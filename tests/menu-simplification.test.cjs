const test=require('node:test'),assert=require('node:assert/strict');
const p=require('../n8n/recommendations/policy.js');
const actor={source:'discord',userId:'111',destinationId:'333',messageId:'444',requestedAt:'2026-10-07T12:00:00Z'};
const now=Date.parse(actor.requestedAt);
const prepare=require('../n8n/telegram-commands/policy.js').prepare;
test('Telegram help navigation uses the clicking actor and cannot become a confirmation',()=>{
 const update={callback_query:{id:'123456789',data:'snake_menu:recommend',from:{id:222},message:{message_id:77,date:1700000000,chat:{id:333},from:{id:111}}}};
 const r=prepare(update,'SnakeBot')[0].json;
 assert.equal(r.userId,222);assert.equal(r.text,'/recommend');assert.equal(r.action,undefined);assert.equal(r.pendingId,undefined);assert.equal(r.messageId,'123456789');
 update.callback_query.data='snake_menu:expiry';const expiry=prepare(update,'SnakeBot')[0].json;
 assert.match(expiry.commandReply,/30 days/);assert.ok(expiry.menuChoices.some(c=>c.action==='extend'));
 update.callback_query.data='snake_menu:authorize';assert.equal(prepare(update,'SnakeBot')[0].json.text,'confirmation');
});
function results(){let row={...p.record(actor,now),id:12};row=p.transition(row,{...actor,action:'rec_movie'},now,'a').record;row=p.transition(row,{...actor,action:'rec_genre_0'},now,'b').record;return p.completed(row,[{media:{tmdbId:9,title:'Alien',year:1979},available:false,reason:'Science fiction.'}],[]);}
test('change genre keeps the same owned menu and never generates media',()=>{
 const row=results();assert.ok(p.card(row,now).choices.some(c=>c.action==='rec_change'));
 const changed=p.transition(row,{...actor,action:'rec_change'},now,'c');
 assert.equal(changed.generate,false);assert.equal(changed.preview,null);
 assert.match(p.card(changed.record,now).text,/choose a genre/);
 assert.equal(changed.record.expiresAt,row.expiresAt);
 assert.throws(()=>p.transition(row,{...actor,userId:'222',action:'rec_change'},now,'c'));
});
test('more suggestions exclude shown titles and cannot exceed five generations',()=>{
 let row=results();assert.ok(p.card(row,now).choices.some(c=>c.action==='rec_more'));
 for(let i=2;i<=5;i++){
  const next=p.transition(row,{...actor,action:'rec_more'},now,'claim'+i);
  assert.equal(next.generate,true);assert.equal(next.record.state,'processing');
  const rec=JSON.parse(next.record.contextJson).recommendation;
  assert.equal(rec.generations,i);
  const g=p.generation(actor,[],'movie','any',rec.seen);
  assert.match(g.prompt,/Alien/);assert.ok(p.verified({title:'Alien',year:1979,reason:'Again'},[{tmdbId:9,title:'Alien',year:1979}],'movie','any',g.history)===null);
  row=p.completed(next.record,[{media:{tmdbId:9+i,title:'Film '+i,year:2000},reason:'A film.'}],[]);
 }
 assert.ok(!p.card(row,now).choices.some(c=>c.action==='rec_more'));
 assert.throws(()=>p.transition(row,{...actor,action:'rec_more'},now,'limit'));
 const genre=p.transition(row,{...actor,action:'rec_change'},now,'change').record;
 assert.throws(()=>p.transition(genre,{...actor,action:'rec_genre_1'},now,'limit'));
});
