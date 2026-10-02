// Overlay a fresh private export. Reuse production nodes and their exact table bindings.
const fs=require('node:fs'),path=require('node:path');

function overlay(source){
 if(!Array.isArray(source))throw new Error('Expected n8n workflow export array');
 const select=id=>{
  const matches=source.filter(w=>w.id===id);
  if(matches.length!==1)throw new Error('Missing or duplicate workflow '+id);
  return JSON.parse(JSON.stringify(matches[0]));
 };
 const worker=select('snakeRetentionMediaV1'),store=select('snakeRetentionStoreV1');
 const node=(w,name)=>{
  const matches=w.nodes.filter(n=>n.name===name);
  if(matches.length!==1)throw new Error('Missing or duplicate node '+name);
  return matches[0];
 };
 const call=node(worker,'Persist Retention Records');
 const failClosed=n=>{
  if(n.continueOnFail===true||n.disabled===true||n.onError&&n.onError!=='stopWorkflow')throw new Error('Persistence safety node must run and fail closed: '+n.name);
 };
 failClosed(call);
 const guard=node(store,'Validate Store Owner');
 failClosed(guard);
 if(guard.type!=='n8n-nodes-base.code'||guard.parameters.mode&&guard.parameters.mode!=='runOnceForAllItems')throw new Error('Store guard must validate the complete batch');
 if(call.type!=='n8n-nodes-base.executeWorkflow'||call.parameters.workflowId.value!==store.id||call.parameters.options?.waitForSubWorkflow!==true||call.onError&&call.onError!=='stopWorkflow')
  throw new Error('Persistence must await the existing store and fail closed');
 for(const [name,operation] of [['Read Store Lock','get'],['Upsert Retention Record','upsert']]){
  const n=node(store,name);
  failClosed(n);
  if(n.type!=='n8n-nodes-base.dataTable'||n.parameters.operation!==operation||!n.parameters.dataTableId?.value||n.onError&&n.onError!=='stopWorkflow')
   throw new Error('Persistence requires native fail-closed Data Table nodes');
 }
 node(worker,'Records To Persist').parameters.jsCode=`const p=$json;
const records=p.mode==='enabled'?p.records:p.records.filter(r=>r.kind==='file');
return records.length?[{json:{owner:p.owner,records:records.map(r=>({...r,owner:p.owner}))}}]:[{json:{skip:true}}];`;
 node(worker,'Has Retention Record?').parameters.conditions.conditions[0].leftValue='={{ Array.isArray($json.records) && $json.records.length > 0 }}';
 call.parameters.mode='once';
 node(store,'Validate Store Owner').parameters.jsCode=`const locks=$input.all().filter(x=>x.json.key);
const input=$('Record Input').first().json;
if(locks.length!==1||locks[0].json.key!=='global'||!input.owner||locks[0].json.owner!==input.owner)
 throw new Error('Retention write requires lock');
const records=Object.prototype.hasOwnProperty.call(input,'records')?input.records:[input];
if(!Array.isArray(records)||!records.length)throw new Error('Empty or invalid retention batch');
const keys=new Set();
for(const r of records){
 if(!r||r.owner!==input.owner||typeof r.key!=='string'||!r.key||typeof r.kind!=='string'||!r.kind||typeof r.payloadJson!=='string'||keys.has(r.key))
  throw new Error('Invalid retention record or owner');
 JSON.parse(r.payloadJson);
 keys.add(r.key);
}
return records.map(r=>({json:r}));`;
 for(const w of [store,worker]){
  w.active=false;w.pinData={};
  for(const key of ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived'])delete w[key];
 }
 return [store,worker];
}

function generate(sourceFile,outDir){
 const workflows=overlay(JSON.parse(fs.readFileSync(sourceFile,'utf8').replace(/^\uFEFF/,'')));
 fs.mkdirSync(outDir,{recursive:true,mode:0o700});
 for(const w of workflows){
  const file=path.join(outDir,w.name+'.json');
  fs.writeFileSync(file,JSON.stringify(w,null,2)+'\n',{mode:0o600});
  fs.chmodSync(file,0o600);
 }
 return workflows.length;
}
module.exports={overlay,generate};
if(require.main===module){
 if(process.argv.length!==4)throw new Error('Usage: node build.cjs CURRENT_PRIVATE_EXPORT.json PRIVATE_OUTPUT_DIR');
 console.log('Generated '+generate(process.argv[2],process.argv[3])+' retention workflows');
}
