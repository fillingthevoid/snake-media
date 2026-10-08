const {test}=require('node:test'),a=require('node:assert/strict');
const p=require('../n8n/notification-buttons/policy.js');
const retention=require('../n8n/retention-controls/policy.js');
const actor={source:'discord',userId:'2',destinationId:'3',pendingId:'12',action:'notice_7'};
const row={updatedAt:new Date().toISOString(),id:12,source:'discord',destinationId:'3',requestKey:'discord:3:4',payloadJson:JSON.stringify({userId:'2'})};
const req={requestKey:row.requestKey,source:'discord',userId:'2',state:'registered',mediaType:'tv',mediaId:'8',title:'Example'};
test('notification buttons bind original request, owner, destination and fixed operation',()=>{
 for(const [action,days] of [['notice_7',7],['notice_30',30],['notice_keep',undefined]]){
  const out=p.noticeActor({...actor,action},[row],[req],'55');
  const change=retention.prepareChange(out,[req,{...req,requestKey:'same-title-other-request'},{...req,mediaId:'9',requestKey:'sequel',title:'Example II'}]).change;
  a.deepEqual(change.requestKeys,[req.requestKey]);a.equal(change.days,days);
  a.equal(change.operation,days?'extend':'permanent');
 }
});
test('forged and stale notice callbacks fail closed',()=>{
 for(const extra of [{userId:'9'},{source:'telegram'},{destinationId:'9'},{pendingId:'13'},{action:'notice_3650'}])
  a.equal(p.noticeActor({...actor,...extra},[row],[req],'55').status,'notice');
 a.equal(p.noticeActor(actor,[row],[],'55').status,'notice');
 a.equal(p.noticeActor(actor,[row,row],[req],'55').status,'notice');
 a.equal(p.noticeActor(actor,[{...row,payloadJson:'bad'}],[req],'55').status,'notice');
});
test('generated workflows preserve callback paths and durable platform buttons',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const dir=path.join(__dirname,'../n8n/notification-buttons/workflows');
 const workflows=fs.readdirSync(dir).map(f=>JSON.parse(fs.readFileSync(path.join(dir,f),'utf8')));
 a.equal(workflows.length,6);
 const byId=id=>workflows.find(w=>w.id===id),node=(w,name)=>w.nodes.find(n=>n.name===name);
 for(const w of workflows){
  const names=new Set(w.nodes.map(n=>n.name));a.equal(names.size,w.nodes.length);
  for(const [name,ports] of Object.entries(w.connections)){
   a.ok(names.has(name));for(const rows of Object.values(ports))for(const row of rows)for(const edge of row)a.ok(names.has(edge.node),edge.node);
  }
  for(const n of w.nodes)if(n.type==='n8n-nodes-base.code')new Function('$','$json','$input','$execution',n.parameters.jsCode);
 }
 for(const id of ['HXtTzVTrpNZMZVt3','0e67KTcphqxEKNsh']){
  const w=byId(id);a.equal(w.connections['Download Retention Button?'].main[1][0].node,'Resolve Confirmation');
 }
 const sender=byId('snakeTelegramNoticeSendV1');
 const expr=node(sender,'Send Telegram Completion').parameters.inlineKeyboard.slice(3,-2);
 const keys=new Function('$json','return ('+expr+');')({id:12}).rows.flatMap(r=>r.row.buttons);
 a.deepEqual(keys.map(k=>k.additionalFields.callback_data),['snake:12:notice_7','snake:12:notice_30','snake:12:notice_keep']);
 const queue=node(byId('snakeNotificationQueueV1'),'Queue Batch').parameters.jsCode;
 const output=new Function('$input',queue)({all:()=>[{json:{id:12,notificationKey:'k',destinationId:'3',payloadJson:'{}'}}]});
 a.equal(output[0].json.notifications[0].id,'12');
 const child=byId('snakeNoticeRetentionPreviewV1');
 a.ok(!child.nodes.some(n=>/httpRequest|telegram|respondToWebhook/.test(n.type)));
});
