// Use the existing owned title card for ready direct Discord status responses.
const statusReviewBrowser=require('../my-requests/policy.js');
function directStatusContext(actor,groups,status,now=Date.now()){
 const unchanged={valid:false,status};
 if(actor?.source!=='discord'||!Array.isArray(groups)||groups.length!==1||
    !Number.isSafeInteger(status?.availability?.available)||status.availability.available<1)return unchanged;
 const requests=groups[0]?.requests;
 if(!Array.isArray(requests)||!requests.length||requests.some(r=>r.source!==actor.source||r.userId!==actor.userId))return unchanged;
 let record;try{record=statusReviewBrowser.create(actor,requests,now);}catch{return unchanged;}
 if(record.version)return unchanged;
 const context=JSON.parse(record.contextJson);
 if(context.myRequests.titles.length!==1)return unchanged;
 context.myRequests.selected=0;record.contextJson=JSON.stringify(context);
 return {valid:true,record,status};
}
if(typeof module!=='undefined')module.exports={directStatusContext};
