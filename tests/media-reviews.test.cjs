const {test}=require('node:test');const assert=require('node:assert/strict');
const {verdict,reviewOperation}=require('../n8n/media-reviews/policy.js');
const actor={userId:'10',guildId:'20',channelId:'30'};
const config={source:'discord',userId:'10',state:'review',requestKey:'review:config:20',contextJson:JSON.stringify({kind:'config',guildId:'20',channelId:'40'})};
const notice={id:1,source:'discord',destinationId:'30',requestKey:'r',deliveredAt:new Date(1000).toISOString(),deliveredMessageId:'50',payloadJson:JSON.stringify({kind:'expiry_reminder'})};
const request={requestKey:'r',source:'discord',externalId:'90',mediaType:'tv',title:'Test show'};
function op(body,rows=[config],extra={}){return reviewOperation({body:{...actor,...body},rows,notices:[notice],requests:[request],users:['10','11'],owners:['10'],channels:['30'],now:2000,...extra});}
test('exact fractions drive all silly verdict boundaries',()=>{
 assert.match(verdict(0,3).label,/bargain/);assert.match(verdict(1,10).label,/refund/);
 assert.match(verdict(1,4).label,/Popcorn/);assert.match(verdict(1,2).label,/divided/);
 assert.match(verdict(2,3).label,/pretty/);assert.match(verdict(3,4).label,/approves/);
 assert.match(verdict(3,3).label,/All hiss/);assert.match(verdict(1,2).text,/Early verdict/);
 assert.doesNotMatch(verdict(3,4).text,/Early verdict/);
 assert.match(verdict(999,1000).label,/approves/);
});
test('vote replaces the same user key and counts each user once',()=>{
 const a=op({op:'vote',noticeId:'1',vote:'loved',username:'A'});assert.equal(a.reply.loved,1);
 const b=op({op:'vote',noticeId:'1',vote:'not_for_me',username:'A'},[config,a.row]);
 assert.equal(b.row.requestKey,a.row.requestKey);assert.equal(b.reply.loved,0);assert.equal(b.reply.total,1);
 const c=op({op:'vote',noticeId:'1',vote:'loved',userId:'11'},[config,b.row]);assert.equal(c.reply.total,2);
 const d=op({op:'summary',mediaKey:'tv:90',userId:'11'},[config,b.row,c.row]);assert.equal(d.reply.total,2);
});
test('owner setup and original notice destination are enforced',()=>{
 assert.equal(op({op:'setup',targetChannelId:'40',userId:'11'}).reply.error,'denied');
 assert.equal(op({op:'vote',noticeId:'1',vote:'loved',channelId:'41'}).reply.error,'invalid_notice');
 assert.equal(op({op:'vote',noticeId:'1',vote:'loved'},{},{}).reply.error,'invalid_snapshot');
 assert.equal(op({op:'vote',noticeId:'1',vote:'loved'},[config],{now:21601001}).reply.error,'invalid_notice');
});
test('unconfigured and unauthorized requests do not save votes',()=>{
 assert.equal(op({op:'vote',noticeId:'1',vote:'loved'},[]).row,null);
 assert.equal(op({op:'vote',noticeId:'1',vote:'loved',userId:'99'}).reply.error,'denied');
});
test('registered reaction identities are scoped to server and message',()=>{
 const post={...config,requestKey:'p',contextJson:JSON.stringify({kind:'post',guildId:'20',channelId:'40',messageChannelId:'60',messageId:'60',threadId:'60',mediaKey:'tv:90',title:'Test show'})};
 const a=op({op:'vote',postMessageId:'60',channelId:'60',vote:'loved'},[config,post]);assert.equal(a.reply.total,1);
 assert.equal(op({op:'vote',postMessageId:'60',channelId:'61',vote:'loved'},[config,post]).reply.error,'unknown_post');
 assert.equal(op({op:'vote',postMessageId:'60',channelId:'60',guildId:'21',vote:'loved'},[config,post]).row,null);
});
