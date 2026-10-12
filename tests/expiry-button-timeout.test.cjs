const {test}=require('node:test'),a=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {CardStore}=require('../n8n/button-feedback/custom/card-store.js');
const {noticeActor}=require('../n8n/notification-buttons/policy.js');
test('expiry notice cleanup stays at six hours across touches and restarts',()=>{
 const d=fs.mkdtempSync(path.join(os.tmpdir(),'expiry-buttons-'));
 try{
  const file=path.join(d,'cards.json'),s=new CardStore(file);
  const message=action=>({message_id:10,chat:{id:3},text:'Expiry',reply_markup:{inline_keyboard:[[{text:'Extend',callback_data:'snake:12:'+action}]]}});
  s.remember(message('notice_7'),'2',1000);
  const restored=new CardStore(file);a.equal(restored.touch('3',10,'9',2000),false);
  a.equal(restored.touch('3',10,'2',2000),true);
  a.equal(restored.ownedCard('3',10,'2').expiresAt,21601000);
  restored.expire(21600999);a.equal(restored.pending(21600999).length,0);
  restored.expire(21601000);a.equal(restored.pending(21601000).length,1);
  restored.replace(message('confirm'),'2',3000);
  a.equal(restored.ownedCard('3',10,'2').expiresAt,303000);
 }finally{fs.rmSync(d,{recursive:true,force:true});}
});
test('notice authorization accepts five hours and rejects the six-hour boundary',()=>{
 const actor={source:'discord',userId:'2',destinationId:'3',pendingId:'12',action:'notice_7'};
 const row={deliveredAt:new Date(1000).toISOString(),updatedAt:new Date(18001000).toISOString(),id:12,source:'discord',destinationId:'3',requestKey:'r',payloadJson:JSON.stringify({userId:'2'})};
 const request={requestKey:'r',source:'discord',userId:'2',state:'registered',title:'Example'};
 a.equal(noticeActor(actor,[row],[request],'55',18001000).text,'extend Example 7 days');
 a.equal(noticeActor(actor,[row],[request],'55',21601000).clearControls,true);
 a.equal(noticeActor({...actor,userId:'9'},[row],[request],'55',2000).status,'notice');
});
