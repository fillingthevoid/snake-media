// Media presentation metadata derived from native application snapshots.
const LOCAL_JELLYFIN_BASE='';
function jellyfinLinks(item,remoteBase,localBase=''){
 if(!item?.Id)return {};
 const suffix='/web/index.html#!/details?id='+encodeURIComponent(item.Id);
 const result={jellyfinUrl:remoteBase+suffix};
 if(localBase&&localBase!==remoteBase)result.localJellyfinUrl=localBase+suffix;
 return result;
}
function progress(q){
 const total=Number(q.size),left=Number(q.sizeleft);let parts=[];
 if(Number.isFinite(total)&&total>0&&Number.isFinite(left)&&left>=0)parts.push(Math.round(Math.max(0,Math.min(1,(total-left)/total))*100)+'%');
 if(typeof q.timeleft==='string'&&/^[0-9:. ]{1,30}$/.test(q.timeleft))parts.push('ETA '+q.timeleft);
 const quality=q.quality?.quality?.name;if(typeof quality==='string')parts.push(quality.slice(0,100));
 return parts.join(' · ');
}
function poster(media){return (media.images||[]).find(x=>x.coverType==='poster'&&typeof x.remoteUrl==='string'&&/^https:\/\/(image\.tmdb\.org|artworks\.thetvdb\.com)\//.test(x.remoteUrl))?.remoteUrl;}
function completion(c,records,item,media){
 const key=`file:${c.request.mediaType}:${c.request.mediaId}:${c.fileId}`;
 let v;try{v=JSON.parse(records.find(x=>x.key===key)?.payloadJson||'null');}catch{}
 let expiryText='Expiry check pending.';
 if(v&&v.state==='tracked'&&'/data'+v.path===c.jellyfinPath&&Date.parse(v.importedAt)===Date.parse(c.importedAt)&&Number.isFinite(Date.parse(v.checkedAt))){
  if(v.identityProtected||!v.expiresAt||['protected claim','unclaimed','unclaimed episode in shared file'].includes(v.reason))expiryText='Protected / kept permanently; no automatic deletion.';
  else if(Number.isFinite(Date.parse(v.expiresAt)))expiryText='Expiry: '+new Intl.DateTimeFormat('en-US',{timeZone:'America/Los_Angeles',month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(v.expiresAt));
  if(Date.now()-Date.parse(v.checkedAt)>30*60000)expiryText+=' (last retention check is stale; dates may change).';
 }
 return {posterUrl:poster(media),...jellyfinLinks(item,'http://192.168.1.10:8096',LOCAL_JELLYFIN_BASE),expiryText,quality:c.quality};
}
function feedback(r){
 if(r.status==='added')return '✅ Request accepted: '+r.title+'\n'+(r.searchStarted?'🔎 Search started. Checking for an acceptable release; use /status for download updates.':'Search has not been confirmed; use /status for updates.');
 if(r.status==='already_added')return '✅ '+r.title+' is already registered. Use /status to see availability, download progress and expiry.';
 if(r.status==='notice'&&r.actionAccepted===true&&/\bSearch started\b/i.test(r.text||''))return '✅ Request accepted.\n'+r.text+'\nUse /status for download quality, progress and expiry.';
 return r.text;
}
function progressNotice(r,snapshot,notices,now){
 if(!r.requestKey||r.userId==='1'||!['discord','telegram'].includes(r.source)||!Number.isFinite(Date.parse(r.requestedAt)))return null;
 const own=notices.filter(n=>n.requestKey===r.requestKey);
 if(own.some(n=>!n.notificationKey.includes(':progress:')))return null;
 const text=String(snapshot.text||'');
 const downloading=snapshot.progressState==='downloading';
 const waiting=snapshot.progressState==='waiting'&&now-Date.parse(r.requestedAt)>=10*60000;
 if(!downloading&&!waiting)return null;
 const state=downloading?'downloading':'no-release',notificationKey=r.requestKey+':progress:'+state;
 if(own.some(n=>n.notificationKey===notificationKey))return null;
 const label=downloading?'⬇️ Download started.':'🔎 No acceptable release is downloading yet. Snake Media will continue looking.';
 const payload={text:(label+'\n\n'+text).slice(0,1800),userId:r.userId,messageId:r.messageId,retentionControls:false};
 return {notificationKey,requestKey:r.requestKey,fileKey:'progress:'+state,source:r.source,destinationId:r.destinationId,payloadJson:JSON.stringify(payload),state:'pending',attempts:0,nextAttemptAt:new Date(now).toISOString(),deliveredAt:null,deliveredMessageId:''};
}
function completionExists(c,notices){
 const key=c.request.requestKey+':'+(c.mediaType==='tv'?'tv-ready':c.fileKey);
 return notices.some(r=>r.notificationKey===key || (c.mediaType==='tv'&&r.requestKey===c.request.requestKey&&r.state==='delivered'&&!String(r.notificationKey).includes(':progress:')));
}
function scopedQueue(requests,episodes,queue,records=[]){
 const r=requests[0];
 if(r.mediaType==='movie')return queue.filter(q=>q.movieId===Number(r.mediaId));
 const ids=new Set(requests.flatMap(x=>JSON.parse(x.episodeIdsJson||'[]')).map(String));
 const keys=new Set(requests.map(x=>'request:'+x.requestKey));
 for(const row of records){
  if(!keys.has(row.key))continue;
  const saved=JSON.parse(row.payloadJson);
  for(const id of saved.episodeIds||[])ids.add(String(id));
 }
 const seasons=new Set(episodes.filter(e=>ids.has(String(e.id))&&Number.isSafeInteger(e.seasonNumber)&&e.seasonNumber>0).map(e=>e.seasonNumber));
 return queue.filter(q=>q.seriesId===Number(r.mediaId)&&(q.episodeId?ids.has(String(q.episodeId)):Number.isSafeInteger(q.seasonNumber)&&seasons.has(q.seasonNumber)));
}
if(typeof module!=='undefined')module.exports={progress,poster,completion,feedback,progressNotice,completionExists,scopedQueue,jellyfinLinks};
