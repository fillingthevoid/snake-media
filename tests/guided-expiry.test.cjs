const {test}=require('node:test'),a=require('node:assert/strict');
const p=require('../n8n/retention-controls/policy.js');
const actor={source:'telegram',userId:'2',destinationId:'3',text:'/extend'};
const req=(id,title,extra={})=>({source:'telegram',userId:'2',state:'registered',requestKey:'req:'+id,mediaType:'tv',mediaId:String(id),title,...extra});
const pending=g=>({id:12,source:'telegram',userId:'2',destinationId:'3',state:'preview',choice:'',claimId:'',expiresAt:'2099-01-01',contextJson:JSON.stringify({retentionGuide:g})});
test('bare commands list only actor owned media and group duplicate claims',()=>{
 const out=p.prepareChange(actor,[req(4,'Example'),req(4,'Example',{requestKey:'duplicate'}),req(5,'Private',{userId:'9'}),req(6,'Discord',{source:'discord'}),req(7,'Gone',{state:'deleted'})]);
 a.equal(out.guide.candidates.length,1);a.deepEqual(out.guide.candidates[0].requestKeys,['req:4','duplicate']);
 a.equal(p.prepareChange({...actor,text:'/keep'},[]).notice.includes('requests'),true);
});
test('title matching folds ampersands punctuation and accents but prefers exact title',()=>{
 const rows=[req(4,'The Adventures of Pete & Pete'),req(5,'Example'),req(6,'Example II'),req(7,'Amélie')];
 a.equal(p.prepareChange({...actor,text:'/extend pete and pete 7 days'},rows).change.mediaId,'4');
 a.equal(p.prepareChange({...actor,text:'/keep Amelie permanently'},rows).change.mediaId,'7');
 a.equal(p.prepareChange({...actor,text:'/keep Example permanently'},rows).change.mediaId,'5');
 a.equal(p.prepareChange({...actor,text:'/keep !!! permanently'},rows).guide,undefined);
 a.equal(p.prepareChange({...actor,text:'/extend exam 30 days'},rows).guide.candidates.length,2);
});
test('guides page safely and require title then duration then confirmation',()=>{
 const g=p.prepareChange(actor,Array.from({length:12},(_,i)=>req(i+10,'Title '+i))).guide;
 let row=pending(g);const card=p.changeCard(row);a.equal(card.choices.length,10);
 let out=p.guideAction(row,{...actor,action:'retpage_1'},Date.now());
 row={...row,...out};a.equal(p.changeCard(row).choices.filter(c=>c.action.startsWith('rettitle_')).length,4);
 out=p.guideAction(row,{...actor,action:'rettitle_8'},Date.now());row={...row,...out};
 a.deepEqual(p.changeCard(row).choices.map(c=>c.action),['retdays_7','retdays_30','cancel']);
 a.throws(()=>p.guideAction(row,{...actor,action:'confirm'},Date.now()));
 out=p.guideAction(row,{...actor,action:'retdays_30'},Date.now());row={...row,...out};
 a.equal(JSON.parse(row.contextJson).retentionChange.days,30);
 a.deepEqual(p.changeCard(row).choices.map(c=>c.action),['confirm','cancel']);
});
test('guides reject forged actions wrong owner wrong chat and expiry',()=>{
 const row=pending(p.prepareChange(actor,[req(4,'Example')]).guide);
 for(const action of ['confirm','rettitle_999','retpage_999','retdays_3650'])a.throws(()=>p.guideAction(row,{...actor,action},Date.now()));
 a.throws(()=>p.guideAction(row,{...actor,userId:'9',action:'cancel'},Date.now()));
 a.throws(()=>p.guideAction(row,{...actor,destinationId:'9',action:'cancel'},Date.now()));
 a.throws(()=>p.guideAction({...row,expiresAt:'2020-01-01'},{...actor,action:'cancel'},Date.now()));
});
test('ambiguous explicit extension preserves chosen days and still requires confirmation',()=>{
 const g=p.prepareChange({...actor,text:'/extend exam 14 days'},[req(4,'Example'),req(5,'Example II')]).guide;
 const out=p.guideAction(pending(g),{...actor,action:'rettitle_1'},Date.now());
 const c=JSON.parse(out.contextJson).retentionChange;a.equal(c.days,14);a.equal(c.mediaId,'5');a.equal(out.state,'preview');
});
