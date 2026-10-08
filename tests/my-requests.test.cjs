const test=require('node:test'),assert=require('node:assert/strict');
const p=require('../n8n/my-requests/policy.js');
const actor={source:'discord',userId:'111',destinationId:'333',messageId:'444',requestedAt:'2026-10-08T03:00:00Z'};
const now=Date.parse(actor.requestedAt);
const rows=Array.from({length:12},(_,i)=>({...actor,state:'registered',requestKey:'r'+i,mediaType:i%2?'tv':'movie',mediaId:String(i+10),title:'Same title',requestedAt:new Date(now-i*1000).toISOString()}));
test('owned title menu groups claims by immutable media ID and pages without metadata reads',()=>{
 const row={...p.create(actor,[...rows,rows[0],{...rows[0],userId:'222',title:'PRIVATE'}],now),id:7};
 const c=p.card(row,now);assert.equal(c.choices.filter(c=>c.action.startsWith('mr_title_')).length,8);
 assert.equal(JSON.parse(row.contextJson).myRequests.titles.length,12);assert.equal(row.contextJson.includes('PRIVATE'),false);
 const next=p.advance(row,{...actor,action:'mr_page_1'},now,'x');assert.equal(next.statusActor,null);
 assert.equal(p.card(next.record,now).choices.filter(c=>c.action.startsWith('mr_title_')).length,4);
 assert.throws(()=>p.advance(next.record,{...actor,action:'mr_title_0'},now,'y'));
});
test('selection reads exact media identity and expiry actions still enter confirmation',()=>{
 let row={...p.create(actor,rows,now),id:7};
 const pick=p.advance(row,{...actor,action:'mr_title_1'},now,'a');row=pick.record;
 assert.equal(pick.statusActor.mediaId,'11');assert.equal(pick.statusActor.mediaType,'tv');
 assert.deepEqual(p.card(row,now,{version:1,status:'notice',text:'Available',jellyfinUrl:'http://media/web/index.html#!/details?id=abc'}).choices.slice(0,3).map(c=>c.action),['mr_refresh','mr_extend','mr_keep']);
 const keep=p.advance(row,{...actor,action:'mr_keep'},now,'b');assert.equal(keep.changeActor.text,'keep');assert.equal(keep.changeActor.mediaId,'11');assert.equal(keep.record.state,'preview');
 const second=p.advance(keep.record,{...actor,action:'mr_extend'},now,'c');assert.equal(second.changeActor.mediaId,'11');assert.notEqual(second.changeActor.messageId,keep.changeActor.messageId);
 assert.throws(()=>p.advance(row,{...actor,userId:'222',action:'mr_refresh'},now,'c'));
 assert.throws(()=>p.advance(row,{...actor,destinationId:'334',action:'mr_refresh'},now,'c'));
 const late=p.advance(row,{...actor,action:'mr_refresh'},now+31*60000,'c');assert.equal(late.statusActor.mediaId,'11');
});
test('legacy open navigation stays active after weeks while handled menus remain closed',()=>{
 const later=now+60*86400000,row={...p.create(actor,rows,now),id:7,expiresAt:new Date(now+30*60000).toISOString()};
 assert.equal(p.card(row,later).status,'confirmation');
 const next=p.advance(row,{...actor,action:'mr_title_0'},later,'late');assert.equal(next.statusActor.mediaId,'10');assert.ok(Date.parse(next.record.expiresAt)>later);
 const retire=require('../n8n/maintenance/policy.js').retireChoice;
 assert.equal(retire({...row,createdAt:actor.requestedAt},later),null);
 const closed={...row,state:'cancelled'};assert.throws(()=>p.advance(closed,{...actor,action:'mr_title_0'},later,'x'));
 assert.equal(p.card(closed,later).status,'notice');
 assert.equal(retire({...row,contextJson:'{}',createdAt:actor.requestedAt},later).state,'expired');
});
test('targeted retention keeps same-title movies and shows separate and skips repeated title entry',()=>{
 const r=require('../n8n/retention-controls/policy.js');
 const a={...actor,mediaType:'tv',mediaId:'11',text:'extend'};
 const g=r.prepareChange(a,rows);assert.equal(g.guide.candidates.length,1);assert.equal(g.guide.selected,0);
 const keep=r.prepareChange({...a,text:'keep'},rows);assert.equal(keep.change.mediaId,'11');assert.equal(keep.change.operation,'permanent');
 assert.ok(r.prepareChange({...a,userId:'222'},rows).notice);
});
test('saving a Watch address requires the owned settings screen and returns to exact status',()=>{
 let row={...p.create(actor,rows,now),id:7};row=p.advance(row,{...actor,action:'mr_title_0'},now,'a').record;
 assert.throws(()=>p.advance(row,{...actor,action:'wp_local'},now,'b'));
 row=p.advance(row,{...actor,action:'mr_watch'},now,'b').record;
 assert.deepEqual(p.card(row,now).choices.slice(0,3).map(c=>c.action),['wp_local','wp_tailscale','wp_both']);
 assert.throws(()=>p.advance(row,{...actor,action:'mr_keep'},now,'c'));
 assert.throws(()=>p.advance(row,{...actor,userId:'222',action:'wp_local'},now,'c'));
 const choice=p.advance(row,{...actor,action:'wp_local'},now,'c');
 assert.equal(choice.preference.state,'settings');assert.equal(choice.preference.userId,actor.userId);
 assert.equal(choice.preference.requestKey,'watchpref:discord:111');assert.equal(choice.statusActor.mediaId,'10');
 assert.equal(choice.record.state,'preview');
});
