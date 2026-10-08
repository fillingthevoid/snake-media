// Completion transport index. Original request and retention claims stay intact.
function eligible(r){return r.requestKey&&r.state==='registered'&&r.baselineCaptured===true&&r.userId!=='1'&&['discord','telegram'].includes(r.source);}
function completionMarkers(requests,notices,existing){
 return requests.filter(eligible).map(r=>{
  const proof=notices.find(n=>n.requestKey===r.requestKey&&n.source===r.source&&n.destinationId===r.destinationId&&
   ['pending','delivered'].includes(n.state)&&typeof n.notificationKey==='string'&&n.notificationKey.startsWith(r.requestKey+':')&&!n.notificationKey.includes(':progress:'));
  const old=existing.find(x=>x.requestKey===r.requestKey);
  return {requestKey:r.requestKey,source:r.source,userId:r.userId,destinationId:r.destinationId,
   state:proof||old?.state==='complete'?'complete':'pending',queuedAt:proof?.createdAt||old?.queuedAt||null};
 });
}
function pendingBatches(markers){
 const keys=[...new Set(markers.filter(m=>m.state==='pending'&&typeof m.requestKey==='string'&&m.requestKey).map(m=>m.requestKey))],result=[];
 for(let i=0;i<keys.length;i+=200)result.push({keys:keys.slice(i,i+200)});
 return result;
}
function retireChoice(row,now){
 const expiry=Date.parse(row.expiresAt),updated=Date.parse(row.updatedAt||row.createdAt);
 if(!Number.isFinite(expiry)||!Number.isFinite(updated)||row.state==='processing')return null;
 const terminal=['done','cancelled','expired'].includes(row.state);
 if(terminal&&updated<now-90*86400000)return {...row,contextJson:'{}',mediaJson:'{}'};
 if(['preview','seasons'].includes(row.state)&&expiry<now-7*86400000)return {...row,state:'expired',contextJson:'{}',mediaJson:'{}'};
 return null;
}
if(typeof module!=='undefined')module.exports={completionMarkers,pendingBatches,retireChoice};
