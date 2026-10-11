const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {SnakeTelegramControls}=require('../n8n/button-feedback/custom/SnakeTelegramControls.node.js');
const {CardStore}=require('../n8n/button-feedback/custom/card-store.js');
function fixture(t,photo=false){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-edit-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const file=path.join(dir,'cards.json'),store=new CardStore(file);
 const original={message_id:17,chat:{id:333},from:{is_bot:true},reply_markup:{inline_keyboard:[[{text:'Choose',callback_data:'snake:124:season_1'}]]},...(photo?{photo:[{file_id:'existing'}],caption:'Choose seasons'}:{text:'Choose seasons'})};
 store.remember(original,'222');
 const reply={ownerId:'222',chatId:'333',replyText:'Selected: Seasons 1, 2',pendingId:'124',actionAccepted:true,choices:[{label:'Review',action:'review'}],callbackMessage:original,callbackData:'snake:124:season_1',callbackId:'1234'};
 const calls=[];const ctx={getInputData:()=>[{json:reply}],getNodeParameter:(n,i,f)=>({operation:'presentCard',ownerId:'222',stateFile:file}[n]??f),getCredentials:async()=>({accessToken:'123:EXAMPLE'}),helpers:{httpRequest:async o=>{calls.push(o);return {ok:true,result:{...original,reply_markup:o.body.reply_markup,...(o.body.text?{text:o.body.text}:{}),...(o.body.caption?{caption:o.body.caption}:{})}};}}};
 return {reply,original,calls,ctx,store,file};
}
test('accepted season selections edit the original text or poster and replace buttons',async t=>{
 for(const photo of [false,true]){const f=fixture(t,photo);const out=await SnakeTelegramControls.prototype.execute.call(f.ctx);
  assert.equal(f.calls.length,1);assert.ok(f.calls[0].url.endsWith(photo?'/editMessageCaption':'/editMessageText'));
  assert.equal(f.calls[0].body.message_id,17);assert.equal(f.calls[0].body[photo?'caption':'text'],'Selected: Seasons 1, 2');
  assert.deepEqual(f.calls[0].body.reply_markup.inline_keyboard,[[{text:'Review',callback_data:'snake:124:review'}]]);assert.equal(out[0][0].json.result.message_id,17);
 }
});
test('a new recommendation poster edits media even when the old menu was text',async t=>{
 const f=fixture(t);f.reply.posterUrl='https://image.tmdb.org/t/p/new.jpg';await SnakeTelegramControls.prototype.execute.call(f.ctx);
 assert.ok(f.calls[0].url.endsWith('/editMessageMedia'));assert.equal(f.calls[0].body.media.media,f.reply.posterUrl);assert.equal(f.calls[0].body.message_id,17);
});
test('confirmed expiry changes replace the result and remove controls from cleanup state',async t=>{
 const f=fixture(t,true);f.reply.replyText='Kept permanently';f.reply.choices=[];
 await SnakeTelegramControls.prototype.execute.call(f.ctx);assert.deepEqual(f.calls[0].body.reply_markup.inline_keyboard,[]);
 f.store.expire(Date.now()+600000);assert.equal(f.store.pending(Date.now()/1000+1000).length,0);
});
test('transient edit failures never send a replacement or expose tokens',async t=>{
 const f=fixture(t);f.ctx.helpers.httpRequest=async o=>{f.calls.push(o);throw {statusCode:503,message:'https://api.telegram.org/bot123:EXAMPLE/editMessageText'};};
 await assert.rejects(()=>SnakeTelegramControls.prototype.execute.call(f.ctx),e=>e.message==='Telegram card update failed');assert.equal(f.calls.length,1);
});
test('only an explicit missing original permits a replacement with current buttons',async t=>{
 const f=fixture(t);f.ctx.helpers.httpRequest=async o=>{f.calls.push(o);if(f.calls.length===1)throw {statusCode:400,message:'Bad Request: message to edit not found'};return {ok:true,result:{...f.original,message_id:18,text:o.body.text,reply_markup:o.body.reply_markup}};};
 const out=await SnakeTelegramControls.prototype.execute.call(f.ctx);assert.equal(f.calls.length,2);assert.ok(f.calls[1].url.endsWith('/sendMessage'));assert.equal(out[0][0].json.result.message_id,18);
});
test('unchanged edits succeed without a new message',async t=>{
 const f=fixture(t);f.ctx.helpers.httpRequest=async o=>{f.calls.push(o);throw {statusCode:400,message:'Bad Request: message is not modified'};};
 const out=await SnakeTelegramControls.prototype.execute.call(f.ctx);assert.equal(out[0][0].json.result.message_id,17);assert.equal(f.calls.length,1);
});
test('busy or denied selections acknowledge the click without modifying the original',async t=>{
 for(const busy of [true,false]){const f=fixture(t);f.reply.actionAccepted=false;f.reply.busy=busy;await SnakeTelegramControls.prototype.execute.call(f.ctx);assert.ok(f.calls[0].url.endsWith('/answerCallbackQuery'));assert.equal(f.calls.length,1);}
});
test('replacing a notice with expiry confirmation prevents old cleanup clearing the new buttons',t=>{
 const f=fixture(t);f.store.replace({...f.original,reply_markup:{inline_keyboard:[[{text:'Confirm',callback_data:'snake:125:confirm'}]]}},'222');
 f.store.consume('pending:124','222','333');assert.equal(f.store.pending(Date.now()/1000).length,0);
 f.store.consume('pending:125','222','333');assert.equal(f.store.pending(Date.now()/1000).length,1);
});
