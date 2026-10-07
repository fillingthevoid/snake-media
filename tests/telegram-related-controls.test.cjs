const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {SnakeTelegramControls}=require('../n8n/button-feedback/custom/SnakeTelegramControls.node.js');
test('Telegram accepted callbacks queue sibling keyboards and retry without sending messages',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-controls-'));try{
  const file=path.join(dir,'state.json'),node=new SnakeTelegramControls(),calls=[];
  const message=id=>({message_id:id,chat:{id:333},reply_markup:{inline_keyboard:[[{text:'Confirm',callback_data:'snake:13:confirm'}],[{text:'Open',url:'https://jellyfin.example.com'}]]}});
  const context=(operation,m,reply)=>({getInputData:()=>[{json:reply}],getNodeParameter:(name,index,fallback)=>({operation,message:m,ownerId:'111',stateFile:file,callbackData:'snake:13:confirm'}[name]??fallback),getCredentials:async()=>({accessToken:'123:SECRET'}),helpers:{httpRequest:async r=>{calls.push(r);return {ok:true};}}});
  await node.execute.call(context('remember',message(100),{ok:true}));
  await node.execute.call(context('remember',message(101),{ok:true}));
  await node.execute.call(context('clear',message(101),{text:'Denied'}));assert.equal(calls.length,0);
  await node.execute.call(context('clear',message(101),{actionAccepted:true,text:'Saved'}));
  assert.equal(calls.length,1);
  const {CardStore}=require('../n8n/button-feedback/custom/card-store.js');assert.equal(new CardStore(file).pending(Date.now()/1000).length,1);
  await node.execute.call(context('retry',{},{}));assert.equal(calls.length,2);
  assert.equal(calls[1].body.message_id,100);assert.deepEqual(calls[1].body.reply_markup.inline_keyboard,[[{text:'Open',url:'https://jellyfin.example.com'}]]);
  assert.equal(new CardStore(file).pending(Date.now()/1000).length,0);
  assert.ok(calls.every(r=>r.url.endsWith('/editMessageReplyMarkup')));
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
