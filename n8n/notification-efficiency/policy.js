// Queue exclusions let healthy recipients advance past deferred notices.
function queueBatch(rows,excluded=[]){
 const seen=new Set(),skip=new Set(excluded),notifications=[];
 for(const r of rows){
  if(!r.notificationKey||/:tv:\d+:episode:\d+$/.test(r.notificationKey)||seen.has(r.notificationKey)||skip.has(r.notificationKey))continue;
  seen.add(r.notificationKey);
  try{
   const payload=JSON.parse(r.payloadJson);
   if(!payload||typeof payload!=='object'||Array.isArray(payload))continue;
   notifications.push({id:String(r.id),notificationKey:r.notificationKey,destinationId:r.destinationId,payload});
  }catch{}
  if(notifications.length===10)break;
 }
 return {version:1,notifications};
}
function pendingRequests(requests,notices){
 const finished=new Set(notices.filter(n=>['pending','delivered'].includes(n.state)&&
  typeof n.notificationKey==='string'&&!n.notificationKey.includes(':progress:')).map(n=>n.requestKey));
 return requests.filter(r=>r.baselineCaptured&&r.userId!=='1'&&r.state==='registered'&&
  ['discord','telegram'].includes(r.source)&&!finished.has(r.requestKey));
}
if(typeof module!=='undefined')module.exports={queueBatch,pendingRequests};
