const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {CardStore}=require('../n8n/button-feedback/custom/card-store.js');
const {SnakeTelegramControls}=require('../n8n/button-feedback/custom/SnakeTelegramControls.node.js');
test('original Telegram card survives restart and stays scoped to owner and chat',()=>{
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'snake-active-'));try{
 const file=path.join(folder,'cards.json'),s=new CardStore(file);
 s.rememberActive({message_id:9,chat:{id:333},photo:[{}]},'111','4');
 s.rememberActive({message_id:10,chat:{id:333}},'111','4');
 const restarted=new CardStore(file);assert.equal(restarted.active('333','4','111').id,9);
 assert.equal(restarted.active('333','4','222'),null);assert.equal(restarted.active('334','4','111'),null);
 }finally{fs.rmSync(folder,{recursive:true,force:true});}
});
test('Telegram edit is idempotent and transient failures request retry rather than a new post',async()=>{
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'snake-update-'));try{
 const file=path.join(folder,'cards.json'),s=new CardStore(file);s.rememberActive({message_id:9,chat:{id:333},photo:[{}]},'111','4');
 s.remember({message_id:9,chat:{id:333},reply_markup:{inline_keyboard:[[{text:'Confirm',callback_data:'snake:1:confirm'}]]}},'111');s.consume('pending:1','111','333');assert.equal(s.pending(Date.now()/1000).length,1);
 const params={operation:'update',stateFile:file,ownerId:'111',requestMessageId:'4'};
 const reply={id:7,destinationId:'333',text:'Available',retentionControls:true,jellyfinUrl:'https://media.example/web/index.html#!/details?id=abc'};
 const calls=[];const ctx={getInputData:()=>[{json:reply}],getNodeParameter:(n,i,f)=>params[n]??f,getCredentials:async()=>({accessToken:'123:placeholder'}),helpers:{httpRequest:async opt=>{calls.push(opt);return {ok:true,result:{message_id:9,chat:{id:333}}};}}};
 const method=new SnakeTelegramControls().execute;
 let out=(await method.call(ctx))[0][0].json;assert.equal(out.originalCardUpdated,true);assert.equal(out.result.message_id,9);
 assert.match(calls[0].url,/editMessageCaption$/);assert.equal(calls[0].body.message_id,9);assert.equal(calls[0].body.reply_markup.inline_keyboard.flat().length,4);assert.equal(s.pending(Date.now()/1000).length,0);
 ctx.helpers.httpRequest=async()=>{throw Error('private URL must not be emitted');};out=(await method.call(ctx))[0][0].json;
 assert.equal(out.originalCardRetry,true);assert.equal(JSON.stringify(out).includes('private URL'),false);
 ctx.helpers.httpRequest=async()=>{throw {statusCode:400,message:'message is not modified'};};out=(await method.call(ctx))[0][0].json;
 assert.equal(out.originalCardUpdated,true);
 params.ownerId='222';out=(await method.call(ctx))[0][0].json;assert.equal(out.originalCardUpdated,false);assert.equal(out.originalCardRetry,undefined);
 }finally{fs.rmSync(folder,{recursive:true,force:true});}
});
