const test=require('node:test'),assert=require('node:assert/strict');
const p=require('../n8n/my-requests/policy.js');
const now=Date.parse('2026-10-15T15:00:00Z');
const actor={source:'discord',userId:'111',destinationId:'333',messageId:'444',requestedAt:new Date(now).toISOString(),query:'Ninja Turtles'};
const request=(mediaId,title,extra={})=>({...actor,state:'registered',requestKey:'r'+mediaId,mediaType:'movie',mediaId,title,...extra});
const rows=[request('10','Teenage Mutant Ninja Turtles'),request('11','Teenage Mutant Ninja Turtles II'),request('12','Teenage Mutant Ninja Turtles',{mediaType:'tv'}),request('13','The Matrix'),request('99','Ninja Turtles PRIVATE',{userId:'222'}),request('98','Ninja Turtles OTHER PLATFORM',{source:'telegram'})];
const open=(items=rows,a=actor)=>({...p.create(a,items,now),id:7});
const move=(row,action,at=now)=>p.advance(row,{...actor,action},at,'claim');
const status={summaryText:'🎬 Teenage Mutant Ninja Turtles (1990)\nAvailable in Jellyfin.',text:'Full status',availability:{available:1},retentionActions:{canExtend:true,canKeep:true}};

test('selected status includes the year from matching live metadata only',()=>{
 const s=require('../n8n/status/policy.js');
 const input={requests:[rows[0]],records:[],media:{id:10,year:1990},episodes:[],queue:[],library:[],now};
 assert.match(s.describe(input,true).summaryText,/Ninja Turtles \(1990\)/);
 assert.doesNotMatch(s.describe({...input,media:{id:11,year:2000}}),/2000/);
});

test('search opens first owned distinct matching identity and provides exact-ID navigation',()=>{
 let row=open([...rows,rows[0]]),b=JSON.parse(row.contextJson).myRequests;
 assert.equal(b.titles.length,3);assert.equal(b.selected,0);assert.equal(b.titles[0].mediaId,'10');
 let card=p.card(row,now,status);assert.match(card.text,/Match 1 of 3/);assert.match(card.text,/1990/);
 assert.ok(card.choices.some(c=>c.action==='mr_next'));assert.ok(!card.choices.some(c=>c.action==='mr_previous'));
 assert.throws(()=>move(row,'mr_previous'));
 row=move(row,'mr_details').record;
 const next=move(row,'mr_next');row=next.record;
 assert.equal(next.statusActor.mediaId,'11');assert.equal(next.statusActor.query,'');assert.equal(JSON.parse(row.contextJson).myRequests.details,false);
 assert.equal(next.changeActor,null);assert.equal(next.preference,null);
 const keep=move(row,'mr_keep');assert.equal(keep.changeActor.mediaId,'11');
 row=move(row,'mr_next').record;card=p.card(row,now,status);
 assert.match(card.text,/Match 3 of 3/);assert.ok(!card.choices.some(c=>c.action==='mr_next'));assert.throws(()=>move(row,'mr_next'));
 assert.equal(move(row,'mr_previous').statusActor.mediaId,'11');
 assert.equal(JSON.parse(move(row,'mr_back').record.contextJson).myRequests.selected,2);
});

test('settings and retention handoff preserve selected match and ownership/expiry checks',()=>{
 let row=move(open(),'mr_next',now+1000).record;
 assert.equal(Date.parse(row.expiresAt),now+301000);
 const settings=move(row,'mr_watch').record;
 assert.ok(!p.card(settings,now).choices.some(c=>['mr_next','mr_previous'].includes(c.action)));
 assert.throws(()=>move(settings,'mr_next'));
 assert.equal(move(settings,'mr_back').statusActor.mediaId,'11');
 assert.throws(()=>p.advance(row,{...actor,userId:'222',action:'mr_next'},now,'x'));
 assert.throws(()=>p.advance(row,{...actor,source:'telegram',action:'mr_next'},now,'x'));
 assert.throws(()=>move(row,'mr_next',Date.parse(row.expiresAt)));
 assert.equal(move(row,'mr_close').record.state,'cancelled');
});

test('one and zero matches are direct and friendly; bare list remains a list',()=>{
 const single=open(rows,{...actor,query:'Turtles II'}),c=p.card(single,now,status);
 assert.equal(JSON.parse(single.contextJson).myRequests.selected,0);
 assert.ok(!c.choices.some(c=>['mr_next','mr_previous'].includes(c.action)));
 assert.match(p.create({...actor,query:'Not here'},rows,now).text,/No requests of yours match/);
 const bare=open(rows,{...actor,query:''});assert.equal(JSON.parse(bare.contextJson).myRequests.selected,null);
 assert.ok(p.card(bare,now).choices.some(c=>c.action.startsWith('mr_title_')));
 assert.throws(()=>move(bare,'mr_next'));
});

test('search retains newest request order, filters before the cap, and discloses truncation',()=>{
 const many=Array.from({length:202},(_,i)=>request(String(i+100),'Ninja Turtles '+i,{requestedAt:new Date(now-i*1000).toISOString()}));
 const row=open(many);assert.equal(JSON.parse(row.contextJson).myRequests.titles.length,200);
 assert.match(p.card(row,now,status).text,/first 200/i);
 const filtered=open(many,{...actor,query:'Turtles 201'});assert.equal(JSON.parse(filtered.contextJson).myRequests.titles[0].mediaId,'301');
 const reordered=open([...rows].reverse());assert.equal(JSON.parse(reordered.contextJson).myRequests.titles[0].mediaId,'12');
});
