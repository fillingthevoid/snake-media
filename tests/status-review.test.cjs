const {test}=require('node:test'),assert=require('node:assert/strict');
const {directStatusContext}=require('../n8n/status-review/policy.js');
const browser=require('../n8n/my-requests/policy.js');
const now=Date.parse('2026-10-13T23:00:00Z');
const actor={source:'discord',userId:'10',destinationId:'30',messageId:'40',requestedAt:new Date(now).toISOString(),query:'secret of the ooze'};
const requests=[{source:'discord',userId:'10',mediaType:'movie',mediaId:'100',state:'registered',requestKey:'r',title:'Teenage Mutant Ninja Turtles II: The Secret of the Ooze',requestedAt:actor.requestedAt}];
const status={version:1,status:'notice',text:'Available in Jellyfin',availability:{available:1,total:1},jellyfinUrl:'https://media.example/web/index.html#!/details?id=abc'};
test('direct available title status becomes the same owned interactive title card',()=>{
 const context=directStatusContext(actor,[{requests}],status,now);assert.equal(context.valid,true);
 assert.equal(context.record.userId,'10');assert.equal(JSON.parse(context.record.contextJson).myRequests.selected,0);
 const card=browser.card({...context.record,id:7},now,context.status);
 assert.equal(card.status,'confirmation');assert.ok(card.choices.some(c=>c.action==='mr_review'));assert.equal(card.jellyfinUrl,status.jellyfinUrl);
});
test('noninteractive internal status reads and Telegram do not create request menus',()=>{
 for(const a of [{source:'discord',userId:'10'},{...actor,source:'telegram'},{...actor,messageId:''},{...actor,requestedAt:'bad'}])assert.equal(directStatusContext(a,[{requests}],status,now).valid,false);
 assert.equal(directStatusContext(actor,[{requests}],{...status,availability:{available:0}},now).valid,false);
 assert.equal(directStatusContext(actor,[{requests},{requests}],status,now).valid,false);
 assert.equal(directStatusContext(actor,[{requests:[{...requests[0],userId:'11'}]}],status,now).valid,false);
});
test('review remains visible on an available title detail card',()=>{
 const row={...browser.create(actor,requests,now),id:7};const ctx=JSON.parse(row.contextJson);ctx.myRequests.selected=0;ctx.myRequests.details=true;row.contextJson=JSON.stringify(ctx);
 assert.ok(browser.card(row,now,status).choices.some(c=>c.action==='mr_review'));
});
