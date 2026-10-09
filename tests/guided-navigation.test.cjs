const test=require('node:test'),a=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {CardStore}=require('../n8n/button-feedback/custom/card-store.js');
const commands=require('../n8n/telegram-commands/policy.js');
const {SnakeTelegramControls}=require('../n8n/button-feedback/custom/SnakeTelegramControls.node.js');
test('request navigation and bare command start a title prompt',()=>{
 const m={message_id:4,date:1,chat:{id:333},from:{id:111},text:'/request'};
 a.equal(commands.prepare({message:m},'SnakeBot')[0].json.requestPrompt,true);
 a.equal(commands.prepare({callback_query:{id:'55',from:{id:111},data:'snake_menu:request',message:m}},'SnakeBot')[0].json.requestPrompt,true);
 a.equal(commands.prepare({message:{...m,text:'/request Matrix'}},'SnakeBot')[0].json.text,'add Matrix');
});
test('Telegram prompts survive restart and reject cross-user, stale and repeated replies',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-prompt-'));
 try{let s=new CardStore(path.join(dir,'state.json'));
 s.rememberPrompt({message_id:7,chat:{id:333}},'111',1000);
 s=new CardStore(s.file);
 a.equal(s.claimPrompt('333',7,'222',2000),'unowned');
 a.equal(s.claimPrompt('333',7,'111',2000),'accepted');
 a.equal(s.claimPrompt('333',7,'111',2001),'handled');
 s.rememberPrompt({message_id:8,chat:{id:333}},'111',1000);
 a.equal(s.claimPrompt('333',8,'111',301000),'expired');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('timeout jobs preserve text and mark timeout separately from handled cleanup',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-expiry-'));
 try{const s=new CardStore(path.join(dir,'state.json'));
 s.remember({message_id:7,chat:{id:333},text:'My requests',reply_markup:{inline_keyboard:[[{text:'Refresh',callback_data:'snake:12:mr_refresh'}]]}},'111',1000);
 s.expire(301000);const j=s.pending(302)[0];a.equal(j.expired,true);a.equal(j.message.text,'My requests');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('waiting and available status explain the next action',()=>{
 const p=require('../n8n/status/policy.js'),r={mediaType:'movie',mediaId:'8',title:'Example',requestKey:'r',retentionDays:7};
 const x={requests:[r],records:[],media:{id:8},episodes:[],queue:[],library:[],now:Date.now()};
 a.match(p.describe(x),/No action needed/);
 x.media.movieFile={id:1,path:'/movies/a',dateAdded:'2026-10-09'};x.library=[{Id:'a',Path:'/data/movies/a'}];
 a.match(p.describe(x),/Watch now/);
});
test('transport prompt replies preserve commands and clear prompts only for owned valid titles',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-guided-'));
 try{
 const file=path.join(dir,'state.json'),store=new CardStore(file),node=new SnakeTelegramControls();
 const original={message_id:7,chat:{id:333},text:'What would you like to watch?\nReply with a movie or series title within 5 minutes.'};store.rememberPrompt(original,'111');
 const ctx=(owner,text)=>({getInputData:()=>[{json:{text,userId:owner,chatId:333}}],getNodeParameter:(name,i,f)=>({operation:'resolvePrompt',ownerId:owner,stateFile:file,message:{text,chat:{id:333},reply_to_message:original}}[name]??f)});
 a.equal((await node.execute.call(ctx('222','Alien')))[0][0].json.commandReply.includes('another account'),true);
 a.equal((await node.execute.call(ctx('111','/help')))[0][0].json.text,'/help');
 a.equal((await node.execute.call(ctx('111','Alien')))[0][0].json.text,'add Alien');
 a.ok((await node.execute.call(ctx('111','Alien')))[0][0].json.commandReply);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('Telegram timeout edit adds reopening hint while preserving caption and Watch URL',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-hint-'));
 try{const file=path.join(dir,'state.json'),store=new CardStore(file),node=new SnakeTelegramControls(),calls=[];
 store.remember({message_id:7,chat:{id:333},caption:'Example — available',reply_markup:{inline_keyboard:[[{text:'Refresh',callback_data:'snake:12:mr_refresh'},{text:'Watch',url:'https://jellyfin.example.com'}]]}},'111',0);
 const ctx={getInputData:()=>[{json:{}}],getNodeParameter:(n,i,f)=>({operation:'retry',stateFile:file}[n]??f),getCredentials:async()=>({accessToken:'123:EXAMPLE'}),helpers:{httpRequest:async r=>{calls.push(r);return {ok:true};}}};
 await node.execute.call(ctx);a.equal(calls.length,1);a.ok(calls[0].url.endsWith('/editMessageCaption'));a.match(calls[0].body.caption,/Example — available[\s\S]*Menu expired/);a.equal(calls[0].body.reply_markup.inline_keyboard[0][0].text,'Watch');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
