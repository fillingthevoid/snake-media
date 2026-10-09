// Saved evidence for navigation only. Final status and amendments recheck services.
function decode(row){try{return JSON.parse(row.payloadJson);}catch{return null;}}
function fresh(stamp,now){const n=Date.parse(stamp);return Number.isFinite(n)&&n<=now+60000&&n>=now-30*60000;}
function scopedFiles(requests,records,now){
 if(!requests.length)return [];
 const r=requests[0],ids=new Set(),keys=new Set(requests.map(r=>r.requestKey));
 for(const request of requests){try{for(const id of JSON.parse(request.episodeIdsJson||'[]'))ids.add(String(id));}catch{}}
 for(const row of records){const v=decode(row);if(row.key?.startsWith('request:')&&keys.has(row.key.slice(8))&&v?.mediaType===r.mediaType&&String(v.mediaId)===String(r.mediaId))for(const id of v.episodeIds||[])ids.add(String(id));}
 return records.filter(row=>row.key?.startsWith(`file:${r.mediaType}:${r.mediaId}:`)).map(decode).filter(v=>v&&v.state==='tracked'&&v.mediaType===r.mediaType&&String(v.mediaId)===String(r.mediaId)&&Number.isSafeInteger(v.fileId)&&v.fileId>0&&typeof v.path==='string'&&Number.isFinite(Date.parse(v.importedAt))&&fresh(v.checkedAt,now)&&(r.mediaType==='movie'||v.episodeIds?.some(id=>ids.has(String(id)))));
}
function category(requests,{records=[],events=[],notices=[]},now){
 const r=requests[0],files=scopedFiles(requests,records,now),keys=new Set(requests.map(r=>r.requestKey));
 const timed=files.filter(f=>!f.identityProtected&&Number.isFinite(Date.parse(f.expiresAt)));
 const expiry=timed.length?Math.min(...timed.map(f=>Date.parse(f.expiresAt))):null;
 const ready=files.some(f=>notices.some(n=>keys.has(n.requestKey)&&['pending','delivered'].includes(n.state)&&!String(n.notificationKey).includes(':progress:')&&Date.parse(n.deliveredAt||n.createdAt)>=Date.parse(f.importedAt)&&(r.mediaType==='movie'?n.fileKey===`movie:${r.mediaId}`:f.episodeIds?.some(id=>n.fileKey===`tv:${r.mediaId}:episode:${id}`))));
 if(expiry!==null&&expiry<=now+3*86400000)return {category:'expiring',expiry,ready};
 if(ready)return {category:'ready',expiry,ready:true};
 const ids=new Set(requests.flatMap(r=>{try{return JSON.parse(r.episodeIdsJson||'[]').map(String);}catch{return [];}})),newest=new Map();
 for(const event of events){
  if(event.mediaType!==r.mediaType||String(event.mediaId)!==String(r.mediaId)||!fresh(event.receivedAt,now)||Date.parse(event.receivedAt)<Math.min(...requests.map(r=>Date.parse(r.requestedAt))))continue;
  let scope;try{scope=r.mediaType==='movie'?['movie']:JSON.parse(event.episodeIdsJson).map(String).filter(id=>ids.has(id));}catch{continue;}
  for(const id of scope)if(!newest.has(id)||Date.parse(event.receivedAt)>Date.parse(newest.get(id).receivedAt))newest.set(id,event);
 }
 return {category:[...newest.values()].some(e=>e.state==='downloading')?'downloading':'other',expiry};
}
function expiryPreview(change,files,now){
 if(change.operation!=='extend')return '';
 const eligible=(files||[]).filter(f=>fresh(f.checkedAt,now)&&!f.identityProtected&&Number.isFinite(Date.parse(f.expiresAt)));
 if(!eligible.length)return 'The proposed date is unavailable until the next expiry check. Confirming rechecks eligible files.';
 const dates=eligible.map(f=>Math.max(now,Date.parse(f.expiresAt))+change.days*86400000);
 const label=n=>new Intl.DateTimeFormat('en-US',{timeZone:'America/Los_Angeles',month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(n);
 const first=Math.min(...dates),last=Math.max(...dates);
 return 'Proposed expiry'+(dates.length>1?' dates':'')+': '+label(first)+(last!==first?' to '+label(last):'')+'.\nBased on the last expiry check; final confirmation rechecks files. Protected files stay protected.';
}
if(typeof module!=='undefined')module.exports={scopedFiles,category,expiryPreview};
