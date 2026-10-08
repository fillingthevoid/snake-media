const test=require('node:test'),a=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {CardStore}=require('../n8n/button-feedback/custom/card-store.js');
const p=require('../n8n/my-requests/policy.js');
const actor={source:'discord',userId:'111',destinationId:'333',messageId:'444',requestedAt:'2026-10-08T12:00:00Z'};
const now=Date.parse(actor.requestedAt);
test('expired download controls reject only after stored ownership is proved',()=>{
 const p=require('../n8n/notification-buttons/policy.js'),r={id:12,source:'discord',destinationId:'333',requestKey:'r',updatedAt:new Date(now).toISOString(),payloadJson:JSON.stringify({userId:'111'})};
 const req={requestKey:'r',source:'discord',userId:'111',state:'registered',title:'Example'};
 a.equal(p.noticeActor({...actor,pendingId:'12',action:'notice_keep'},[r],[req],'c',now+299999).source,'discord');
 const expired=p.noticeActor({...actor,pendingId:'12',action:'notice_keep'},[r],[req],'c',now+300000);
 a.equal(expired.clearControls,true);a.equal(expired.status,'notice');
 a.notEqual(p.noticeActor({...actor,userId:'222',pendingId:'12',action:'notice_keep'},[r],[req],'c',now+300000).clearControls,true);
});
test('owned request browsing renews five minutes and refuses expired selections',()=>{
 let row={...p.create(actor,[{...actor,state:'registered',requestKey:'r',mediaType:'tv',mediaId:'9',title:'Example'}],now),id:12};
 a.equal(Date.parse(row.expiresAt),now+300000);
 row=p.advance(row,{...actor,action:'mr_title_0'},now+240000,'c').record;
 a.equal(Date.parse(row.expiresAt),now+540000);
 a.throws(()=>p.advance(row,{...actor,action:'mr_refresh'},now+540000,'d'));
 a.throws(()=>p.advance(row,{...actor,userId:'222',action:'mr_refresh'},now+250000,'e'));
});
test('Telegram menu deadlines survive restart, renew only for owner, keep links',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-timeout-'));
 try{
  const file=path.join(dir,'state.json');let s=new CardStore(file);
  const m={message_id:100,chat:{id:333},reply_markup:{inline_keyboard:[[{text:'Help',callback_data:'snake_menu:help'},{text:'Watch',url:'https://jellyfin.example.com'}]]}};
  s.remember(m,'111',100000);s.expire(399999);a.equal(s.pending(400).length,0);
  a.equal(s.touch('333',100,'222',350000),false);a.equal(s.touch('333',100,'111',350000),true);
  s=new CardStore(file);s.expire(400000);a.equal(s.pending(400).length,0);
  a.equal(s.touch('333',100,'111',650000),false);s.expire(650000);
  const jobs=s.pending(650);a.equal(jobs.length,1);a.deepEqual(jobs[0].message.reply_markup.inline_keyboard,[[{text:'Watch',url:'https://jellyfin.example.com'}]]);
  s.finish('333',100);a.equal(s.pending(650).length,0);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
