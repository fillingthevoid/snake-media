const {test}=require('node:test'),a=require('node:assert/strict');
const p=require('../n8n/expiry-reminders/policy.js');
const now=Date.parse('2026-10-10T12:00:00Z'),hour=3600000;
const req={requestKey:'discord:3:4',source:'discord',userId:'2',destinationId:'3',messageId:'4',state:'registered',baselineCaptured:true,mediaType:'tv',mediaId:'8',title:'Example'};
const file=(id,expiry=now+24*hour)=>({key:`file:tv:8:${id}`,kind:'file',payloadJson:JSON.stringify({state:'tracked',mediaType:'tv',mediaId:'8',fileId:id,path:`/tv/Example/${id}.mkv`,importedAt:'2026-09-10T12:00:00Z',episodeIds:[String(id)],checkedAt:new Date(now).toISOString(),expiresAt:new Date(expiry).toISOString(),identityProtected:false,deadlines:{[req.requestKey+':'+id]:new Date(expiry).toISOString()}})});
const run=(records=[file(1)],requests=[req],notices=[],mode='enabled')=>p.planReminders({records,requests,notices,mode,now});
test('24h boundary, grouped episode reminder, requester scope, and idempotence',()=>{
 const out=run([file(1),file(2)]);a.equal(out.length,1);
 const n=out[0],payload=JSON.parse(n.payloadJson);a.equal(n.source,'discord');a.equal(n.destinationId,'3');a.equal(payload.userId,'2');a.match(payload.text,/2 episodes/);a.match(payload.text,/Extend/);
 a.equal(run([file(1),file(2)],[req],[{...n,state:'delivered'}]).length,0);
 a.equal(run([file(1,now+24*hour+1)]).length,0);a.equal(run([file(1,now)]).length,0);
});
test('permanent, deleted, identity protected, stale and preview records do not remind',()=>{
 a.equal(run(undefined,undefined,undefined,'preview').length,0);
 for(const extra of [{expiresAt:null},{state:'deleted'},{identityProtected:true},{checkedAt:new Date(now-hour).toISOString()}]){
 const r=file(1);r.payloadJson=JSON.stringify({...JSON.parse(r.payloadJson),...extra});a.equal(run([r]).length,0);
 }
 a.equal(run(undefined,[{...req,userId:'9',requestKey:'other'}]).length,0);
});
test('effective shared-file deadline controls reminders and explicit extension permits later reminder',()=>{
 const n=run()[0];a.equal(run([file(1,now+48*hour)],[req],[n]).length,0);
 const later=p.planReminders({records:[{...file(1,now+48*hour),payloadJson:JSON.stringify({...JSON.parse(file(1,now+48*hour).payloadJson),checkedAt:new Date(now+24*hour).toISOString()})}],requests:[req],notices:[{...n,state:'delivered'}],mode:'enabled',now:now+24*hour});a.equal(later.length,1);a.notEqual(later[0].notificationKey,n.notificationKey);
});
test('Telegram shares policy; malformed/duplicate records fail closed',()=>{
 const r={...req,source:'telegram',requestKey:'telegram:3:4'};const f=file(1);const d=JSON.parse(f.payloadJson);d.deadlines={[r.requestKey+':1']:d.expiresAt};f.payloadJson=JSON.stringify(d);
 a.equal(run([f],[r])[0].source,'telegram');a.equal(run([file(1),file(1)]).length,0);a.equal(run([{...file(1),payloadJson:'bad'}]).length,0);
});
test('reminders do not suppress completion tracking',()=>{
 const efficiency=require('../n8n/notification-efficiency/policy.js');a.equal(efficiency.pendingRequests([req],[run()[0]]).length,1);
});

test('reminder choice includes all grouped owned claims and excludes another user',()=>{
 const p=require('../n8n/notification-buttons/policy.js'),ret=require('../n8n/retention-controls/policy.js');const now=Date.now();
 const actor={source:'discord',userId:'2',destinationId:'3',pendingId:'12',action:'notice_7'};
 const req={requestKey:'a',source:'discord',userId:'2',state:'registered',mediaType:'tv',mediaId:'8',title:'Example'};
 const row={id:12,updatedAt:new Date(now).toISOString(),source:'discord',destinationId:'3',requestKey:'a',payloadJson:JSON.stringify({userId:'2',kind:'expiry_reminder',requestKeys:['a','b','other']})};
 const out=p.noticeActor(actor,[row],[req,{...req,requestKey:'b'},{...req,userId:'9',requestKey:'other'}],'55',now);
 a.deepEqual(ret.prepareChange(out,[req,{...req,requestKey:'b'},{...req,userId:'9',requestKey:'other'}]).change.requestKeys,['a','b']);
});
test('queued warning is invalid after expiry changes or deletion is paused',()=>{
 const n=run()[0];a.equal(p.reminderValid(n,[file(1)],'enabled',now),true);
 a.equal(p.reminderValid(n,[file(1,now+48*hour)],'enabled',now),false);
 a.equal(p.reminderValid(n,[file(1)],'preview',now),false);
 a.equal(p.reminderValid(n,[],'enabled',now),false);
 a.equal(p.reminderValid({payloadJson:'{}'},[],'preview',now),true);
});
