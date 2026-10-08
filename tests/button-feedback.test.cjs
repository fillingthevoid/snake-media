const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
const rows=()=>JSON.parse(fs.readFileSync(path.join(root,'config-templates/n8n-current-media-workflows.json')));
function run(id,name,input,refs={}){
 const code=rows().find(w=>w.id===id).nodes.find(n=>n.name===name).parameters.jsCode;
 return new Function('$json','$input','$',code)(input,{first:()=>({json:input}),all:()=>[{json:input}]},name=>({first:()=>({json:refs[name]}),all:()=>[{json:refs[name]}]}))[0].json;
}
test('owned download preview acknowledges selection but denied notice never clears controls',()=>{
 const owned={version:1,status:'confirmation',text:'Preview',pendingId:'15',choices:[{label:'Confirm',action:'confirm'}]};
 const r=run('snakeNoticeRetentionPreviewV1','Notice Result',owned,{'Resolve Notice Owner':{source:'discord',text:'extend Example 7 days'}});
 assert.equal(r.actionAccepted,true);assert.equal(r.preserveOriginalControls,true);assert.match(r.text,/Selected/);assert.match(r.text,/Confirm/);
 const denied=run('snakeNoticeRetentionPreviewV1','Notice Result',{version:1,status:'notice',text:'Denied'},{'Resolve Notice Owner':{version:1,status:'notice'}});
 assert.notEqual(denied.actionAccepted,true);assert.notEqual(denied.clearControls,true);
});
test('only persisted amendments report saved expiry and no-op returns useful feedback',()=>{
 const event={operation:'extend',title:'Example',files:[{minimumExpiry:'2026-10-20T12:00:00Z'}]};
 let r=run('snakeRetentionChangeApplyV1','Retention Change Result',{}, {'Plan Retention Amendment':{payloadJson:JSON.stringify(event)}});
 assert.equal(r.retentionUpdated,true);assert.match(r.text,/expiry/i);assert.ok(!r.text.includes('\\n'));
 r=run('snakeRetentionChangeApplyV1','Retention Change Result',{}, {'Plan Retention Amendment':{payloadJson:JSON.stringify({...event,operation:'permanent',files:[]})}});
 assert.equal(r.retentionUpdated,true);assert.match(r.text,/permanently/);
 r=run('snakeRetentionChangeApplyV1','Retention Change Result',{}, {'Plan Retention Amendment':{version:1,status:'notice',text:'No eligible files'}});
 assert.notEqual(r.retentionUpdated,true);assert.match(r.text,/No eligible files/);
});
test('stale owned handled cards clear; other owners and processing keep controls',()=>{
 const w=rows().find(w=>w.id==='snakeConfirmMediaV1'),code=w.nodes.find(n=>n.name==='Validate Action').parameters.jsCode;
 const actor={source:'discord',userId:'2',destinationId:'3',action:'confirm'};
 const row={source:'discord',userId:'2',destinationId:'3',state:'done',contextJson:'{}',expiresAt:new Date(Date.now()+60000).toISOString()};
 const exec=r=>new Function('$input','$','$execution',code)({first:()=>({json:r})},()=>({first:()=>({json:actor})}),{id:'1'})[0].json;
 assert.equal(exec(row).clearControls,true);assert.notEqual(exec({...row,userId:'9'}).clearControls,true);assert.notEqual(exec({...row,state:'processing'}).clearControls,true);
});
test('Telegram text and photo callbacks enter the safe markup editor',()=>{
 const w=rows().find(w=>w.id==='0e67KTcphqxEKNsh');
 const gate=w.nodes.find(n=>n.name==='Owned Text Card Cleanup?').parameters.conditions.conditions[0].leftValue;
 const expression=gate.slice(3,-2);
 const evaluate=(reply,message)=>new Function('$json','$','return '+expression)(reply,()=>({first:()=>({json:{callback_query:{message}}})}));
 assert.equal(evaluate({actionAccepted:true},{message_id:10,photo:[{}]}),true);
 assert.equal(evaluate({actionAccepted:true,preserveOriginalControls:true},{message_id:10,photo:[{}]}),false);
 assert.equal(evaluate({actionAccepted:true,busy:true},{message_id:10,text:'Card'}),false);
 assert.equal(evaluate({},{message_id:10,text:'Card'}),false);
 assert.equal(w.nodes.find(n=>n.name==='Clear Telegram Text Controls').type,'CUSTOM.snakeTelegramControls');
});
test('Telegram markup editing removes callbacks on text/photos, keeps links, and hides API errors',async()=>{
 const {SnakeTelegramControls}=require('../n8n/button-feedback/custom/SnakeTelegramControls.node.js');
 const node=new SnakeTelegramControls();
 for(const content of [{text:'Ready'},{photo:[{}],caption:'Ready'}]){
  const calls=[];const message={...content,message_id:10,chat:{id:20},reply_markup:{inline_keyboard:[[{text:'Open',url:'https://jellyfin.example.com'}],[{text:'Extend',callback_data:'snake:12:notice_7'}]]}};
  const ctx={getInputData:()=>[{json:{actionAccepted:true,text:'Selected'}}],getNodeParameter:()=>message,getCredentials:async()=>({baseUrl:'https://api.telegram.org',accessToken:'123:SECRET'}),helpers:{httpRequest:async options=>{calls.push(options);return {ok:true,result:true};}}};
  const out=await node.execute.call(ctx);
  assert.equal(calls.length,1);assert.deepEqual(calls[0].body.reply_markup,{inline_keyboard:[[{text:'Open',url:'https://jellyfin.example.com'}]]});assert.equal(out[0][0].json.telegramControlsCleared,true);
  ctx.helpers.httpRequest=async()=>{throw Error('https://api.telegram.org/bot123:SECRET/editMessageReplyMarkup failed');};
  const failed=await node.execute.call(ctx);assert.equal(failed[0][0].json.telegramControlsCleared,false);assert.ok(!JSON.stringify(failed).includes('SECRET'));assert.equal(failed[0][0].json.text,'Selected');
  ctx.helpers.httpRequest=async()=>{throw Object.assign(Error('400 - Bad Request: message is not modified'),{statusCode:400});};
  const unchanged=await node.execute.call(ctx);assert.equal(unchanged[0][0].json.telegramControlsCleared,true);
  calls.length=0;ctx.getInputData=()=>[{json:{actionAccepted:true,busy:true}}];await node.execute.call(ctx);assert.equal(calls.length,0);
  ctx.getInputData=()=>[{json:{actionAccepted:true,preserveOriginalControls:true}}];await node.execute.call(ctx);assert.equal(calls.length,0);
  ctx.getInputData=()=>[{json:{text:'Denied'}}];ctx.helpers.httpRequest=async options=>{calls.push(options);return {ok:true};};
  await node.execute.call(ctx);assert.equal(calls.length,0);
  ctx.getInputData=()=>[{json:{actionAccepted:true}}];ctx.getNodeParameter=()=>({...message,message_id:0});
  const invalid=await node.execute.call(ctx);assert.equal(calls.length,0);assert.equal(invalid[0][0].json.telegramControlsCleared,false);
 }
});
