const {test}=require('node:test'),assert=require('node:assert/strict');
const p=require('../n8n/my-requests/policy.js'),r=require('../n8n/media-reviews/policy.js');
const now=Date.parse('2026-10-13T12:00:00Z');
const menu={id:7,source:'discord',userId:'10',destinationId:'30',state:'preview',expiresAt:new Date(now+300000).toISOString(),contextJson:JSON.stringify({myRequests:{selected:0,titles:[{mediaType:'tv',mediaId:'100',title:'A'}]}})};
const request={source:'discord',userId:'10',state:'registered',requestKey:'r',mediaType:'tv',mediaId:'100',externalId:'90',title:'A'};
const config={source:'discord',state:'review',requestKey:'review:config:20',contextJson:JSON.stringify({kind:'config',guildId:'20',channelId:'40'})};
const body={userId:'10',channelId:'30',guildId:'20',myRequestsId:'7',op:'resolve'};
function op(change={},extra={}){return r.reviewOperation({body:{...body,...change},rows:[config],notices:[],requests:[request],menus:[menu],availability:{available:1,total:10},users:['10','11'],owners:['10'],channels:['30'],now,...extra});}
test('Review appears only for live available Discord titles including partial seasons',()=>{
 const card=p.card(menu,now,{text:'A',availability:{available:1,total:10}});
 assert.ok(card.choices.some(c=>c.action==='mr_review'));
 for(const status of [{text:'A',availability:{available:0}},{text:'A'},null])assert.ok(!p.card(menu,now,status).choices.some(c=>c.action==='mr_review'));
 assert.ok(!p.card({...menu,source:'telegram'},now,{text:'A',availability:{available:1}}).choices.some(c=>c.action==='mr_review'));
});
test('owned menu selection resolves external identity without needing an expiry notice',()=>{
 const result=op();assert.equal(result.reply.ok,true);assert.equal(result.reply.mediaKey,'tv:90');assert.equal(result.row,null);
 const vote=op({op:'vote',expectedMediaKey:'tv:90',vote:'loved'});assert.equal(vote.reply.total,1);
 assert.equal(op({op:'vote',expectedMediaKey:'movie:90',vote:'loved'}).reply.error,'invalid_menu');
});
test('opening review renews only the owned menu deadline and preserves its selection',()=>{
 const result=op({op:'open'});assert.equal(result.row.state,'preview');
 assert.equal(result.row.contextJson,menu.contextJson);assert.equal(result.row.expiresAt,new Date(now+300000).toISOString());
 assert.equal(result.menuOriginal.contextJson,menu.contextJson);
});
test('review menu authorization expiry identity and current availability fail closed',()=>{
 assert.equal(op({userId:'11'}).reply.error,'invalid_menu');
 assert.equal(op({channelId:'31'}).reply.error,'invalid_menu');
 assert.equal(op({}, {now:now+300000}).reply.error,'invalid_menu');
 assert.equal(op({}, {availability:{available:0}}).reply.error,'unavailable');
 assert.equal(op({}, {availability:null}).reply.error,'unavailable');
 assert.equal(op({}, {menus:[{...menu,contextJson:JSON.stringify({myRequests:{selected:null,titles:[{}]}})}]}).reply.error,'invalid_menu');
 assert.equal(op({}, {requests:[{...request,userId:'11'}]}).reply.error,'invalid_menu');
});
test('registered starter lists are owner-only paginated and read-only',()=>{
 const posts=Array.from({length:26},(_,i)=>({...config,requestKey:'p'+i,contextJson:JSON.stringify({kind:'post',guildId:'20',mediaKey:'tv:'+i,channelId:'40',messageChannelId:'40',messageId:String(100+i),threadId:String(200+i)})}));
 const a=op({op:'posts',myRequestsId:undefined},{rows:[config,...posts]});assert.equal(a.reply.posts.length,25);assert.equal(a.reply.nextCursor,25);assert.equal(a.row,null);
 assert.equal(op({op:'posts',userId:'11',myRequestsId:undefined},{rows:posts}).reply.error,'denied');
 const b=op({op:'posts',cursor:25,myRequestsId:undefined},{rows:posts});assert.equal(b.reply.posts.length,1);assert.equal(b.reply.nextCursor,null);
});
