// Resolve notification controls from stored ownership, never from a client title.
function noticeActor(actor,notices,requests,executionId){
 const denied={version:1,status:'notice',text:'This download notice is unavailable or belongs to another requester. Use an extend or keep command for your own requests.'};
 if(!['notice_7','notice_30','notice_keep'].includes(actor.action)||!/^\d+$/.test(String(actor.pendingId)))return denied;
 const matches=notices.filter(r=>String(r.id)===String(actor.pendingId));
 if(matches.length!==1)return denied;
 const n=matches[0];let payload;try{payload=JSON.parse(n.payloadJson);}catch{return denied;}
 if(!payload||actor.userId==='1'||n.source!==actor.source||String(n.destinationId)!==actor.destinationId||payload.userId!==actor.userId)return denied;
 const rows=requests.filter(r=>r.requestKey===n.requestKey&&r.source===actor.source&&r.userId===actor.userId&&r.state==='registered');
 if(rows.length!==1||typeof rows[0].title!=='string'||!rows[0].title.trim())return denied;
 const title=rows[0].title.replace(/\s+/g,' ').trim();
 const text=actor.action==='notice_keep'?`keep ${title} permanently`:`extend ${title} ${actor.action==='notice_7'?7:30} days`;
 return {source:actor.source,userId:actor.userId,destinationId:actor.destinationId,
  requestKey:n.requestKey,messageId:`notice:${n.id}:${actor.action}:${executionId}`,text};
}
if(typeof module!=='undefined')module.exports={noticeActor};
