// Queue exclusions let healthy recipients advance past deferred notices.
function queueBatch(rows,excluded=[],afterId=null){
 const seen=new Set(),skip=new Set(excluded),notifications=[];
 if(afterId!==null&&(typeof afterId!=='string'||!(/^[1-9][0-9]{0,19}$/).test(afterId)))throw Error('Invalid queue cursor');
 const ordered=rows.filter(r=>(/^[1-9][0-9]{0,19}$/).test(String(r.id)))
  .sort((a,b)=>BigInt(a.id)<BigInt(b.id)?-1:BigInt(a.id)>BigInt(b.id)?1:0);
 let nextCursor=null;
 for(const r of ordered){
  if(afterId!==null&&BigInt(r.id)<=BigInt(afterId))continue;
  if(!r.notificationKey||/:tv:\d+:episode:\d+$/.test(r.notificationKey)||seen.has(r.notificationKey)||skip.has(r.notificationKey))continue;
  seen.add(r.notificationKey);
  try{
   const payload=JSON.parse(r.payloadJson);
   if(!payload||typeof payload!=='object'||Array.isArray(payload))continue;
   notifications.push({id:String(r.id),notificationKey:r.notificationKey,destinationId:r.destinationId,payload});
  }catch{}
  if(notifications.length===10){nextCursor=String(r.id);break;}
 }
 return {version:1,notifications,nextCursor};
}
function pendingRequests(requests,notices){
 const finished=new Set(notices.filter(n=>['pending','delivered'].includes(n.state)&&
  typeof n.notificationKey==='string'&&!n.notificationKey.includes(':progress:')&&!n.notificationKey.includes(':expiry:')).map(n=>n.requestKey));
 return requests.filter(r=>r.baselineCaptured&&r.userId!=='1'&&r.state==='registered'&&
  ['discord','telegram'].includes(r.source)&&!finished.has(r.requestKey));
}
if(typeof module!=='undefined')module.exports={queueBatch,pendingRequests};
