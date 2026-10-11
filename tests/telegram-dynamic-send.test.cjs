const test=require('node:test'),assert=require('node:assert/strict');
const {SnakeTelegramControls}=require('../n8n/button-feedback/custom/SnakeTelegramControls.node.js');
function context(mode='photo'){
 const calls=[];
 return {calls,getInputData:()=>[{json:{chatId:'333',replyText:'Choose seasons',posterUrl:'https://image.tmdb.org/t/p/poster.jpg',keyboard:{rows:[{row:{buttons:[{text:'Season 1',additionalFields:{callback_data:'snake:124:season_1'}},{text:'Season 2',additionalFields:{callback_data:'snake:124:season_2'}}]}},{row:{buttons:[{text:'Review',additionalFields:{callback_data:'snake:124:review'}}]}}]}}}],getNodeParameter:(n,i,f)=>({operation:'sendCard',sendMode:mode}[n]??f),getCredentials:async()=>({accessToken:'123:EXAMPLE'}),helpers:{httpRequest:async o=>{calls.push(o);return {ok:true,result:{message_id:17,chat:{id:333},reply_markup:o.body.reply_markup}};}}};
}
test('dynamic poster and text cards send every generated button',async()=>{
 for(const mode of ['photo','text']){const ctx=context(mode);const out=await SnakeTelegramControls.prototype.execute.call(ctx);assert.equal(ctx.calls.length,1);assert.equal(ctx.calls[0].body.reply_markup.inline_keyboard.flat().length,3);assert.equal(out[0][0].json.result.message_id,17);assert.ok(ctx.calls[0].url.endsWith(mode==='photo'?'/sendPhoto':'/sendMessage'));}
});
test('invalid keyboards are rejected before delivery',async()=>{
 const ctx=context();const input=ctx.getInputData();input[0].json.keyboard.rows[0].row.buttons[0].additionalFields.callback_data='x'.repeat(65);ctx.getInputData=()=>input;
 await assert.rejects(()=>SnakeTelegramControls.prototype.execute.call(ctx));assert.equal(ctx.calls.length,0);
});
test('delivery failures never expose credentials',async()=>{
 const ctx=context('text');ctx.helpers.httpRequest=async()=>{throw Error('https://api.telegram.org/bot123:EXAMPLE/sendMessage');};
 await assert.rejects(()=>SnakeTelegramControls.prototype.execute.call(ctx),e=>e.message==='Telegram card delivery failed');
});

test('failed confirmation poster routes to text with all confirmation controls',async()=>{
 const workflows=require('../config-templates/n8n-current-media-workflows.json');
 const workflow=workflows.find(w=>w.id==='snakeTelegramCardV1');
 const gate=workflow.nodes.find(n=>n.name==='Recommendation Photo Failed?').parameters.conditions.conditions[0].leftValue;
 const photoFailed=new Function('$json','return ('+gate.slice(3,-2)+');');
 for(const failure of ['exception','unconfirmed']){
  const ctx=context(),input=ctx.getInputData()[0].json;
  input.replyText='Doug (1991)\nSelected: Seasons 3\nConfirm this title and selection?';
  input.keyboard.rows=['confirm','back','wrong','cancel'].map(action=>({row:{buttons:[{text:action,additionalFields:{callback_data:'snake:127:'+action}}]}}));
  ctx.getInputData=()=>[{json:input}];
  ctx.helpers.httpRequest=async()=>{if(failure==='exception')throw Error('https://api.telegram.org/bot123:EXAMPLE/sendPhoto');return {ok:false,description:'private upstream error'};};
  const out=await SnakeTelegramControls.prototype.execute.call(ctx),failed=out[0][0];
  assert.equal(photoFailed(failed.json),true,'the deployed fallback gate must select the text branch');
  assert.deepEqual(failed.pairedItem,{item:0});
  assert.equal(failed.json.error,'Telegram card delivery failed');
  assert.equal(JSON.stringify(failed).includes('123:EXAMPLE'),false);
  assert.equal(JSON.stringify(failed).includes('private upstream error'),false);
  const text=context('text');text.getInputData=()=>[failed];
  const sent=await SnakeTelegramControls.prototype.execute.call(text);
  assert.equal(text.calls[0].body.text,input.replyText);
  assert.deepEqual(text.calls[0].body.reply_markup.inline_keyboard.flat().map(b=>b.callback_data),['snake:127:confirm','snake:127:back','snake:127:wrong','snake:127:cancel']);
  assert.equal(sent[0][0].json.result.message_id,17);
 }
});
