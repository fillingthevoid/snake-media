// Shared n8n expiry policy. No media scans, transport, or deletion here.
const REMINDER_WINDOW=24*3600000, MAX_SNAPSHOT_AGE=30*60000;
function reminderData(row){try{return JSON.parse(row.payloadJson);}catch{return null;}}
function reminderFiles(records,now){
 const seen=new Set();for(const r of records)if(r.key){if(seen.has(r.key))return [];seen.add(r.key);}
 return records.filter(r=>r.kind==='file').map(r=>({...reminderData(r),key:r.key})).filter(d=>
  d.state==='tracked'&&!d.identityProtected&&['movie','tv'].includes(d.mediaType)&&
  Number.isSafeInteger(d.fileId)&&d.fileId>0&&typeof d.path==='string'&&
  d.path.startsWith(d.mediaType==='movie'?'/movies/':'/tv/')&&!d.path.includes('/../')&&
  Number.isFinite(Date.parse(d.importedAt))&&d.checkedAt&&Date.parse(d.checkedAt)<=now+60000&&
  Date.parse(d.checkedAt)>=now-MAX_SNAPSHOT_AGE&&Date.parse(d.expiresAt)>now&&
  Date.parse(d.expiresAt)<=now+REMINDER_WINDOW&&d.deadlines&&typeof d.deadlines==='object');
}
function reminderValid(row,records,mode,now=Date.now()){
 const p=reminderData(row);if(p?.kind!=='expiry_reminder')return true;
 if(mode!=='enabled'||!Array.isArray(p.expiryFiles)||!p.expiryFiles.length)return false;
 const files=reminderFiles(records,now);
 return p.expiryFiles.every(f=>files.some(d=>d.key===f.key&&d.path===f.path&&
  d.importedAt===f.importedAt&&d.expiresAt===f.expiresAt));
}
function planReminders({requests,records,notices,mode,now=Date.now()}){
 if(mode!=='enabled'||!Number.isFinite(now))return [];
 const files=reminderFiles(records,now),groups=new Map(),existing=new Set(notices.map(n=>n.notificationKey));
 for(const r of requests){
  if(!r.baselineCaptured||r.state!=='registered'||r.userId==='1'||!['discord','telegram'].includes(r.source)||
   !r.requestKey||!r.title||!r.destinationId||!r.messageId)continue;
  const owned=files.filter(d=>d.mediaType===r.mediaType&&String(d.mediaId)===String(r.mediaId)&&
   Object.keys(d.deadlines).some(k=>k.startsWith(r.requestKey+':')));
  for(const d of owned){
   const groupKey=JSON.stringify([r.source,r.userId,r.destinationId,r.mediaType,String(r.mediaId)]);
   if(!groups.has(groupKey))groups.set(groupKey,{r,files:new Map(),requestKeys:new Set()});
   groups.get(groupKey).files.set(d.key,d);groups.get(groupKey).requestKeys.add(r.requestKey);
  }
 }
 const result=[];
 for(const {r,files:map,requestKeys} of groups.values()){
  const fs=[...map.values()].sort((a,b)=>a.key.localeCompare(b.key));
  // Each file/deadline is notified once, even when the rest of a batch changes.
  const fresh=fs.filter(d=>!notices.some(n=>{const p=reminderData(n);return p?.kind==='expiry_reminder'&&
   n.source===r.source&&p.userId===r.userId&&n.destinationId===r.destinationId&&
   p.expiryFiles?.some(f=>f.key===d.key&&f.expiresAt===d.expiresAt&&f.importedAt===d.importedAt);}));
  if(!fresh.length)continue;
  const earliest=Math.min(...fresh.map(d=>Date.parse(d.expiresAt)));
  const key=`${r.source}:expiry:${r.userId}:${r.mediaType}:${r.mediaId}:${earliest}`;
  if(existing.has(key))continue;
  const count=new Set(fresh.flatMap(d=>d.episodeIds||[])).size;
  const subject=r.mediaType==='tv'?`${count} episode${count===1?'':'s'} of ${r.title}`:r.title;
  const text=`⏳ ${subject}\n\nScheduled for automatic deletion within 24 hours (earliest: ${new Date(earliest).toISOString().replace('T',' ').replace(':00.000Z',' UTC')}).\n\nWant more time? Extend 7 days, extend 30 days, or keep permanently.\nButtons last 6 hours; /extend and /keep remain available.`;
  result.push({notificationKey:key,requestKey:r.requestKey,fileKey:fresh[0].key,source:r.source,
   destinationId:r.destinationId,payloadJson:JSON.stringify({kind:'expiry_reminder',newMessage:true,text,
    userId:r.userId,messageId:r.messageId,retentionControls:true,requestKeys:[...requestKeys],
    expiryFiles:fresh.map(d=>({key:d.key,path:d.path,importedAt:d.importedAt,expiresAt:d.expiresAt}))}),
   state:'pending',attempts:0,nextAttemptAt:new Date(now).toISOString(),deliveredAt:null,deliveredMessageId:''});
 }
 return result;
}
if(typeof module!=='undefined')module.exports={planReminders,reminderValid};
