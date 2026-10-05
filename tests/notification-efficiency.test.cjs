const {test}=require('node:test'),a=require('node:assert/strict');
const {queueBatch,pendingRequests}=require('../n8n/notification-efficiency/policy.js');
test('deferred notices cannot occupy every slot and starve later recipients',()=>{
 const rows=Array.from({length:12},(_,i)=>({id:i+1,notificationKey:'discord:2:'+i,
 destinationId:'2',payloadJson:JSON.stringify({userId:'3',text:'Ready'})}));
 const batch=queueBatch(rows,rows.slice(0,10).map(r=>r.notificationKey));
 a.deepEqual(batch.notifications.map(r=>r.id),['11','12']);
});
test('completion polling ignores finished requests but keeps progress-only notices pending',()=>{
 const requests=['movie','tv','waiting','progress'].map((key,i)=>({requestKey:key,mediaType:i===0?'movie':'tv',
 mediaId:'7',source:'discord',userId:'3',state:'registered',baselineCaptured:true}));
 const notices=[{requestKey:'movie',notificationKey:'movie:movie:7',state:'pending'},
 {requestKey:'tv',notificationKey:'tv:tv-ready',state:'delivered'},
 {requestKey:'progress',notificationKey:'progress:progress:downloading',state:'delivered'}];
 a.deepEqual(pendingRequests(requests,notices).map(r=>r.requestKey),['waiting','progress']);
});
test('current workflow filters before library read and retains mutation execution settings',()=>{
 const bundle=JSON.parse(require('node:fs').readFileSync(require('node:path').join(__dirname,'../config-templates/n8n-current-media-workflows.json'),'utf8'));
 const scan=bundle.find(w=>w.id==='snakeCompletionScanV1');
 const n=scan.nodes.find(n=>n.name==='Unfinished Requests');
 const run=new Function('$','$input',n.parameters.jsCode);
 const r={requestKey:'r',mediaType:'movie',mediaId:'7',source:'telegram',userId:'3',state:'registered',baselineCaptured:true};
 const inputs={all:()=>[{json:{requestKey:'r',notificationKey:'r:movie:7',state:'delivered'}}]};
 a.deepEqual(run(()=>({all:()=>[{json:r}]}),inputs),[]);
 a.equal(scan.connections['Completion Notices'].main[0][0].node,'Unfinished Requests');
 a.equal(scan.connections['Unfinished Requests'].main[0][0].node,'One Library Read');
 a.equal(bundle.find(w=>w.id==='snakeStatusInspectV1').settings.saveDataSuccessExecution,'none');
 for(const id of ['snakeRetentionCoordinatorV1','snakeLockRecoveryV1']){
  const w=bundle.find(w=>w.id===id);if(w)a.notEqual(w.settings.saveDataSuccessExecution,'none');
 }
});
