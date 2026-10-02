// Snapshot planner: no I/O. Native n8n nodes persist the plan before API changes.
function planMedia(input) {
 const {requests,records,media,episodes,watched,sessions,now}=input;
 if(!requests.length||!Number.isFinite(now)||!media?.id||!Array.isArray(watched)||!Array.isArray(sessions))throw new Error('Incomplete retention snapshot');
 if(new Set(requests.map(r=>r.requestKey)).size!==requests.length)throw new Error('Duplicate request claims');
 if(requests.some(r=>!Number.isFinite(Date.parse(r.requestedAt))||typeof r.baselineCaptured!=='boolean'||(r.retentionDays!==null&&(!Number.isInteger(r.retentionDays)||r.retentionDays<1||r.retentionDays>3650))))throw new Error('Invalid request claim');
 const saved=new Map();
 for(const row of records){if(!row.key)continue;if(saved.has(row.key))throw new Error('Duplicate retention records');saved.set(row.key,JSON.parse(row.payloadJson));}
 const type=requests[0].mediaType,mediaId=String(media.id),updates=[],monitor=new Set(),search=new Set();
 if(requests.some(r=>r.mediaType!==type||String(r.mediaId)!==mediaId))throw new Error('Media identity mismatch');
 const expired=new Map();
 for(const [key,v] of saved)if(key.startsWith(`file:${type}:${mediaId}:`)&&v.state==='deleted')for(const id of v.episodeIds||[])expired.set(String(id),Math.max(expired.get(String(id))||0,Date.parse(v.deletedAt)));
 const scopes=new Map(),protections=new Map(),managed=new Set();
 for(const r of requests){
  const key='request:'+r.requestKey,profile=saved.get(key);
  const ids=new Set(JSON.parse(r.episodeIdsJson));const before=new Set(JSON.parse(r.preexistingFileIdsJson));
  if(profile){
   if(profile.requestKey!==r.requestKey||profile.mediaType!==type||String(profile.mediaId)!==mediaId)throw new Error('Subscription identity mismatch');
   managed.add(r.requestKey);
   for(const id of profile.episodeIds||[])ids.add(String(id));
   for(const id of profile.protectedFileIds||[])before.add(String(id));
   if(type==='tv')for(const e of episodes){
    if(!belongsToSubscription(e,profile))continue;
    const id=String(e.id);
    if(!ids.has(id)){
     ids.add(id);
     // An already present file discovered by reconciliation stays protected.
     if(e.episodeFileId>0)before.add(String(e.episodeFileId));
     else if(Number.isFinite(Date.parse(e.airDateUtc))&&Date.parse(e.airDateUtc)<=now)search.add(e.id);
    }
    if(!(expired.get(id)>=Date.parse(r.requestedAt)))monitor.add(e.id);
   }
   updates.push({key,kind:'subscription',payloadJson:JSON.stringify({...profile,episodeIds:[...ids],protectedFileIds:[...before]})});
  }
  scopes.set(r.requestKey,ids);protections.set(r.requestKey,before);
 }
 const files=new Map();
 if(type==='movie'){
  if(media.movieFile?.id)files.set(media.movieFile.id,{file:media.movieFile,episodes:[]});
 }else for(const e of episodes){
  if(!Number.isSafeInteger(e.id)||!Number.isInteger(e.seasonNumber)||!Number.isInteger(e.episodeNumber))throw new Error('Incomplete episode metadata');
  if(e.episodeFileId>0&&!e.episodeFile?.id)throw new Error('Missing episode file metadata');
  if(e.episodeFile?.id){const f=e.episodeFile;if(!files.has(f.id))files.set(f.id,{file:f,episodes:[]});files.get(f.id).episodes.push(e);}
 }
 const deletions=[],decisions=[];
 for(const [fileId,group] of files){
  const f=group.file,key=`file:${type}:${mediaId}:${fileId}`,previous=saved.get(key)||{};
  if(!Number.isSafeInteger(fileId)||typeof f.path!=='string'||!f.path.startsWith(type==='movie'?'/movies/':'/tv/')||f.path.includes('/../')||!Number.isFinite(Date.parse(f.dateAdded)))throw new Error('Invalid file identity');
  if(previous.state==='deleted')continue;
  const jellyfinPath='/data'+f.path,covered=group.episodes.map(e=>String(e.id)),claims=[],deadlines={};
  for(const r of requests){
   const edits=[...saved.entries()].filter(([k,e])=>k.startsWith('change:')&&e.version===1&&e.mediaType===type&&e.mediaId===mediaId&&e.requestKeys?.includes(r.requestKey)).map(([,e])=>e);
   const permanent=edits.some(e=>e.operation==='permanent');
   const floors=edits.filter(e=>e.operation==='extend').flatMap(e=>e.files||[]).filter(x=>x.fileId===fileId&&x.path===f.path&&Date.parse(x.importedAt)===Date.parse(f.dateAdded)).map(x=>Date.parse(x.minimumExpiry));
   if(floors.some(x=>!Number.isFinite(x)))throw new Error('Invalid saved amendment');
   const minimumExpiry=floors.length?new Date(Math.max(...floors)).toISOString():null;
   const selected=type==='movie'?[null]:group.episodes.filter(e=>scopes.get(r.requestKey).has(String(e.id)));
   for(const episode of selected){
    const claimKey=r.requestKey+':'+(episode?.id||'movie');
    const played=watched.filter(x=>x.Id&&x.Path===jellyfinPath&&x.UserData?.Played===true&&(!episode||
     (x.ParentIndexNumber===episode.seasonNumber&&Number.isInteger(x.IndexNumber)&&episode.episodeNumber>=x.IndexNumber&&episode.episodeNumber<=(x.IndexNumberEnd||x.IndexNumber))));
    let watchedAt=null;
    for(const x of played){const stamp=Date.parse(x.UserData.LastPlayedDate);const t=Number.isFinite(stamp)&&stamp<=now?stamp:now;watchedAt=Math.min(watchedAt??Infinity,t);}
    const c={baselineCaptured:r.baselineCaptured===true&&managed.has(r.requestKey),
     preexisting:protections.get(r.requestKey).has(String(fileId))||Date.parse(f.dateAdded)<Date.parse(r.requestedAt),
     days:permanent?null:r.retentionDays,minimumExpiry,importedAt:f.dateAdded,watchedAt:watchedAt===null?null:new Date(watchedAt).toISOString(),
     previousDeadline:previous.deadlines?.[claimKey],episodeIds:episode?[String(episode.id)]:[]};
    claims.push(c);
    if(c.days!==null)deadlines[claimKey]=effectiveExpiry(c.importedAt,c.days,c.watchedAt,c.previousDeadline,c.minimumExpiry);
   }
  }
  let decision=fileDecision(claims,covered,now);
  const identityProtected=previous.identityProtected===true||!!(previous.path&&(previous.path!==f.path||Date.parse(previous.importedAt)!==Date.parse(f.dateAdded)));
  if(identityProtected)decision={...decision,due:false,reason:'file identity changed; manual review required'};
  const itemIds=new Set(watched.filter(x=>x.Path===jellyfinPath).map(x=>x.Id));
  if(sessions.some(s=>s.NowPlayingItem&&(!s.NowPlayingItem.Path||s.NowPlayingItem.Path===jellyfinPath||itemIds.has(s.NowPlayingItem.Id))))decision={...decision,due:false,reason:'currently playing or unresolved active session'};
  const payload={...decision,state:'tracked',mediaType:type,mediaId,fileId,path:f.path,importedAt:f.dateAdded,episodeIds:covered,deadlines,identityProtected,checkedAt:new Date(now).toISOString()};
  updates.push({key,kind:'file',payloadJson:JSON.stringify(payload)});decisions.push(payload);
  if(decision.due)deletions.push({...payload,key});
 }
 return {records:updates,monitorIds:[...monitor],searchIds:[...search].filter(id=>monitor.has(id)),deletions,decisions};
}
if(typeof module!=='undefined')module.exports={...module.exports,planMedia};
