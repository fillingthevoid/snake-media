const {test}=require('node:test'),a=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const bundle=()=>JSON.parse(fs.readFileSync(path.join(__dirname,'../config-templates/n8n-current-media-workflows.json')));
test('queue accepts explicit recovered receipts but rejects incomplete and ambiguous acknowledgements',()=>{
 const w=bundle().find(w=>w.id==='snakeNotificationQueueV1');
 const run=body=>new Function('$input',w.nodes.find(n=>n.name==='Validate Queue Action').parameters.jsCode)({first:()=>({json:{body}})})[0].json;
 const ack={action:'ack',notificationKey:'discord:restored',receiptRecovered:true};
 a.equal(run(ack).receiptRecovered,true);
 for(const body of [{...ack,receiptRecovered:false},{...ack,receiptRecovered:'true'},{...ack,messageId:'fake'},{...ack,notificationKey:'other'}, {action:'ack',notificationKey:'discord:restored'}])a.throws(()=>run(body));
 a.equal(run({action:'ack',notificationKey:'discord:restored',messageId:'555'}).messageId,'555');
 const update=w.nodes.find(n=>n.name==='Acknowledge Discord Notice').parameters.columns.value;
 const expression=update.deliveredMessageId.replace(/^=\{\{\s*|\s*\}\}$/g,'');
 a.equal(new Function('$json','return '+expression)(run(ack)), '');
});
test('watch-preference collection preserves nextCursor in the final queue response',()=>{
 const w=bundle().find(w=>w.id==='snakeNotificationQueueV1');
 const node=w.nodes.find(n=>n.name==='Collect Preferred Queue');
 const notices=[{id:'1011',notificationKey:'discord:new'}];
 const result=new Function('$','$input',node.parameters.jsCode)(name=>({first:()=>({json:{nextCursor:'1011'}})}),{all:()=>notices.map(json=>({json}))})[0].json;
 a.equal(result.nextCursor,'1011');a.deepEqual(result.notifications,notices);
});
