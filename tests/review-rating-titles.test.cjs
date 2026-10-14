const {test}=require('node:test'),assert=require('node:assert/strict');
const {verdict,reviewOperation}=require('../n8n/media-reviews/policy.js');
test('rating fields use exact fractions at every title verdict boundary',()=>{
 const bands=[
  [0,'🗑️','Straight to the bargain bin'],[1,'🐍','The snake demands a refund'],[24,'🐍','The snake demands a refund'],
  [25,'🍿','Popcorn carried this one'],[49,'🍿','Popcorn carried this one'],[50,'⚖️','The couch is divided'],
  [51,'👍','Certified pretty good'],[74,'👍','Certified pretty good'],[75,'🔥','The couch approves'],
  [99,'🔥','The couch approves'],[100,'🏆','All hiss, no miss']];
 for(const [loved,emoji,label] of bands){const v=verdict(loved,100);assert.deepEqual(v.rating,{emoji,label});assert.ok(v.text.startsWith(emoji+' '+label));}
});
test('registered lookups supply an unrated title and current rating after each vote',()=>{
 const actor={userId:'10',guildId:'20',channelId:'60',postMessageId:'60'};
 const row=d=>({source:'discord',state:'review',requestKey:d.kind,contextJson:JSON.stringify({...d,guildId:'20'})});
 const post=row({kind:'post',channelId:'40',messageChannelId:'60',messageId:'60',threadId:'60',mediaKey:'movie:90',title:'The Matrix'});
 const op=(body,rows)=>reviewOperation({body:{...actor,...body},rows,notices:[],requests:[],users:['10','11'],owners:['10'],channels:['30']});
 const empty=op({op:'lookup'},[post]);assert.equal(empty.reply.ok,true);assert.deepEqual(empty.reply.rating,{emoji:'💬',label:'Awaiting reviews'});
 const one=op({op:'vote',vote:'loved'},[post]);assert.deepEqual(one.reply.rating,{emoji:'🏆',label:'All hiss, no miss'});
 const split=op({op:'vote',vote:'not_for_me',userId:'11'},[post,one.row]);assert.deepEqual(split.reply.rating,{emoji:'⚖️',label:'The couch is divided'});
 const summary=op({op:'lookup'},[post,one.row,split.row]);assert.deepEqual(summary.reply.rating,split.reply.rating);assert.equal(summary.row,null);
});
