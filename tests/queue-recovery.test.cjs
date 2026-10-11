const {test}=require('node:test'),a=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {queueBatch}=require('../n8n/notification-efficiency/policy.js');
const {CardStore}=require('../n8n/button-feedback/custom/card-store.js');
test('embedded queue validates cursors and advances past delivered backlog',()=>{
 const ws=JSON.parse(fs.readFileSync(path.join(__dirname,'../config-templates/n8n-current-media-workflows.json')));
 const w=ws.find(w=>w.id==='snakeNotificationQueueV1'),nodes=Object.fromEntries(w.nodes.map(n=>[n.name,n]));
 const validate=body=>new Function('$input',nodes['Validate Queue Action'].parameters.jsCode)({first:()=>({json:{body}})})[0].json;
 a.equal(validate({action:'poll',afterNotificationId:'1010'}).afterNotificationId,'1010');
 for(const cursor of ['0','abc',12,'1'.repeat(21)])a.throws(()=>validate({action:'poll',afterNotificationId:cursor}));
 const rows=[{json:{id:1010,notificationKey:'discord:old',payloadJson:'{}'}},{json:{id:1011,notificationKey:'discord:new',payloadJson:'{}'}}];
 const action=validate({action:'poll',afterNotificationId:'1010'});
 const result=new Function('$','$input',nodes['Queue Batch'].parameters.jsCode)(name=>({first:()=>({json:action}),all:()=>name==='Pending Discord Notices'?rows:[]}),{all:()=>rows})[0].json;
 a.deepEqual(result.notifications.map(r=>r.notificationKey),['discord:new']);
 a.equal(validate({action:'ack',notificationKey:'discord:old',messageId:'123'}).action,'ack');
});
test('queue advances beyond a thousand delivered receipts and wraps after reaching the end',()=>{
 const rows=Array.from({length:1011},(_,i)=>({id:i+1,notificationKey:'discord:'+i,destinationId:'333',payloadJson:'{"text":"Ready"}'}));
 const excluded=rows.slice(0,1000).map(r=>r.notificationKey);
 const first=queueBatch(rows,excluded);
 a.equal(first.nextCursor,'1010');
 const second=queueBatch(rows,excluded,first.nextCursor);
 a.deepEqual(second.notifications.map(r=>r.id),['1011']);a.equal(second.nextCursor,null);
 a.equal(queueBatch(rows,excluded,second.nextCursor).notifications[0].id,'1001');
});
test('queue cursor orders decimal IDs numerically even beyond JavaScript precision',()=>{
 const rows=['9007199254740993','10','2'].map(id=>({id,notificationKey:'discord:'+id,payloadJson:'{}'}));
 a.deepEqual(queueBatch(rows,[],'2').notifications.map(r=>r.id),['10','9007199254740993']);
});
test('Telegram exhausted jobs recover after restart with capped retries and retirement',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-recovery-'));
 try{
  const file=path.join(dir,'cards.json');let store=new CardStore(file);
  store.remember({message_id:1,chat:{id:333},reply_markup:{inline_keyboard:[[{text:'Confirm',callback_data:'snake:13:confirm'}]]}},'111',0);
  store.expire(300001);let now=301;
  for(let i=0;i<12;i++){
   a.equal(store.pending(now).length,1);store.defer('333',1,now);
   const job=JSON.parse(fs.readFileSync(file)).jobs[0];
   a.ok(job.retryAt-now>=300&&job.retryAt-now<=3600);a.ok(job.attempts<=5);now=job.retryAt;
  }
  store=new CardStore(file);a.equal(store.pending(now).length,1);
  store.compact(91*86400000);a.equal(JSON.parse(fs.readFileSync(file)).jobs.length,0);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('Telegram legacy twelve-attempt jobs resume while recent jobs survive compaction',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-recovery-'));
 try{
  const file=path.join(dir,'cards.json'),store=new CardStore(file);
  store.transaction(s=>s.jobs.push({chat:'333',id:1,createdAt:Date.now(),attempts:12,retryAt:0,links:[]}));
  a.equal(store.pending(1).length,1);store.compact(Date.now());
  a.equal(store.pending(1).length,1);store.finish('333',1);a.equal(store.pending(1).length,0);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
