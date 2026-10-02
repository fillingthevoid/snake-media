// Read-only status projection. Never calculates or changes retention policy.
function command(text){const m=typeof text==='string'&&text.trim().match(/^\/?status(?:@[A-Za-z0-9_]+)?(?:\s+(.*))?$/i);return m?(m[1]||'').trim().slice(0,200):null;}
function select(rows,actor){
 if(!['discord','telegram'].includes(actor.source)||typeof actor.userId!=='string'||!/^\d+$/.test(actor.userId))throw new Error('Invalid status actor');
 const query=String(actor.query||'').toLowerCase();const groups=new Map();
 for(const r of [...rows].sort((a,b)=>Date.parse(b.requestedAt)-Date.parse(a.requestedAt))){
  if(r.source!==actor.source||r.userId!==actor.userId||r.userId==='1'||r.state!=='registered'||!r.requestKey||!['movie','tv'].includes(r.mediaType)||!/^\d+$/.test(String(r.mediaId))||!String(r.title).toLowerCase().includes(query))continue;
  const key=r.mediaType+':'+r.mediaId;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);
 }
 const values=[...groups.values()];
 if(!values.length)return [{notice:query?'No requests of yours match that title.':'No requests found for your account on this platform.'}];
 if(query&&values.length>1)return [{notice:'Several matches. Use status with a more specific title:\n'+values.slice(0,8).map(rs=>'• '+rs[0].title.slice(0,100)).join('\n')}];
 return values.slice(0,3).map(requests=>({requests}));
}
function dateLabel(stamp){return new Intl.DateTimeFormat('en-US',{timeZone:'America/Los_Angeles',month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(stamp));}
function describe({requests,records,media,episodes,queue,library,now}){
 const r=requests[0],title=String(r.title).replace(/[\r\n]/g,' ').slice(0,100),header=(r.mediaType==='movie'?'🎬 ':'📺 ')+title;
 if(!media||media.id!==Number(r.mediaId))return header+'\nNo longer listed in '+(r.mediaType==='movie'?'Radarr.':'Sonarr.');
 const saved=new Map(records.filter(x=>x.key).map(x=>[x.key,JSON.parse(x.payloadJson)]));
 const ids=new Set(requests.flatMap(x=>JSON.parse(x.episodeIdsJson||'[]').map(String)));
 for(const request of requests){const profile=saved.get('request:'+request.requestKey);if(profile)for(const id of profile.episodeIds||[])ids.add(String(id));}
 const items=r.mediaType==='movie'?[{id:r.mediaId,file:media.movieFile,release:media.digitalRelease||media.physicalRelease||media.inCinemas}]:episodes.filter(e=>ids.has(String(e.id))).map(e=>({...e,file:e.episodeFile,release:e.airDateUtc}));
 const paths=new Set(library.filter(x=>x.Id&&x.Path).map(x=>x.Path));
 const counts={available:0,imported:0,downloading:0,queued:0,unreleased:0,waiting:0,removed:0};const files=new Map();
 for(const item of items){
  if(item.file?.id){files.set(item.file.id,item.file);counts[paths.has('/data'+item.file.path)?'available':'imported']++;continue;}
  const q=queue.find(q=>r.mediaType==='movie'?q.movieId===Number(r.mediaId):q.seriesId===Number(r.mediaId)&&(q.episodeId===item.id||(!q.episodeId&&q.seasonNumber===item.seasonNumber)));
  if(q){counts[String(q.status).toLowerCase()==='downloading'?'downloading':'queued']++;continue;}
  const deleted=r.mediaType==='tv'&&[...saved.entries()].some(([key,v])=>key.startsWith('file:tv:'+r.mediaId+':')&&v.state==='deleted'&&(v.episodeIds||[]).includes(String(item.id)));
  counts[deleted?'removed':Date.parse(item.release)>now?'unreleased':'waiting']++;
 }
 let status;
 if(r.mediaType==='movie')status=counts.available?'✅ Available in Jellyfin':counts.imported?'📥 Imported; waiting for Jellyfin':counts.downloading?'⬇️ Downloading':counts.queued?'⏳ In download queue / awaiting import':counts.unreleased?'📅 Awaiting release':'🔎 Waiting for a release';
 else {const labels={available:'available in Jellyfin',imported:'imported; waiting for Jellyfin',downloading:'downloading',queued:'queued / awaiting import',unreleased:'awaiting release',waiting:'waiting for a release',removed:'previously expired'};status=Object.entries(counts).filter(([,v])=>v).map(([k,v])=>v+' '+labels[k]).join(' · ')||'Episode metadata pending';}
 let protectedCount=0,pending=0,earliest=null,oldest=Infinity,deferred=0;
 for(const file of files.values()){
  const v=saved.get(`file:${r.mediaType}:${r.mediaId}:${file.id}`);
  if(!v||v.state!=='tracked'||v.path!==file.path||Date.parse(v.importedAt)!==Date.parse(file.dateAdded)||!Number.isFinite(Date.parse(v.checkedAt))){pending++;continue;}
  oldest=Math.min(oldest,Date.parse(v.checkedAt));
  if(v.identityProtected||!v.expiresAt||v.reason==='protected claim'||v.reason==='unclaimed'||v.reason==='unclaimed episode in shared file'){protectedCount++;continue;}
  if(!Number.isFinite(Date.parse(v.expiresAt))){pending++;continue;}
  earliest=Math.min(earliest??Infinity,Date.parse(v.expiresAt));
  if(v.reason==='currently playing or unresolved active session')deferred++;
 }
 const lines=[header,status];
 if(earliest!==null)lines.push((r.mediaType==='tv'?'Next episode expiry: ':'Expiry: ')+dateLabel(earliest)+(earliest<=now?' (due; cleanup pending)':''));
 if(protectedCount)lines.push(protectedCount+' protected '+(protectedCount===1?'file':'files')+' — no automatic deletion.');
 if(pending)lines.push('Expiry check pending for '+pending+' '+(pending===1?'file.':'files.'));
 if(!files.size){const days=[...new Set(requests.map(x=>[...saved.entries()].some(([k,e])=>k.startsWith('change:')&&e.version===1&&e.operation==='permanent'&&e.mediaType===r.mediaType&&e.mediaId===String(r.mediaId)&&e.requestKeys?.includes(x.requestKey))?null:x.retentionDays))];lines.push(days.includes(null)?'Permanent/protected request.':days.length===1?`Expiry starts after import (${days[0]} days${r.mediaType==='tv'?' per episode':''}).`:'Expiry starts after import; multiple retention choices apply.');}
 if(Number.isFinite(oldest))lines.push('Retention checked '+dateLabel(oldest)+(now-oldest>30*60000?' — stale; dates may change.':'.'));
 if(deferred)lines.push('Cleanup deferred for active playback.');
 if(r.mediaType==='tv'&&requests.some(x=>saved.has('request:'+x.requestKey)))lines.push('Future regular seasons monitored.');
 return lines.join('\n');
}
if(typeof module!=='undefined')module.exports={command,select,describe};
