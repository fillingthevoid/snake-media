const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),vm=require('node:vm');
const script=path.join(__dirname,'../n8n/polish/retention/build.cjs');
function build(){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-batch-'));
 const names=['Reconcile Media Retention','Store Retention Record'];
 const source=names.map(name=>JSON.parse(fs.readFileSync(path.join(__dirname,'../n8n/retention/workflows/Snake Media - '+name+'.json'))));
 for(const w of source)for(const n of w.nodes)if(n.parameters.dataTableId)n.parameters.dataTableId={__rl:true,mode:'id',value:n.name==='Read Store Lock'?'live-control':'live-records'};
 const output=require(script).overlay(source);
 fs.rmSync(dir,{recursive:true,force:true});
 return {source,output};
}
function run(w,name,input,refs={}){
 const code=w.nodes.find(n=>n.name===name).parameters.jsCode;
 return JSON.parse(JSON.stringify(vm.runInNewContext('(function(){'+code+'})()',{
  $json:input[0],$input:{all:()=>input.map(json=>({json})),first:()=>({json:input[0]})},
  $:name=>({first:()=>({json:refs[name]})})
 })));
}
const record=(key,owner='12')=>({key,owner,kind:'file',payloadJson:JSON.stringify({state:'tracked',due:true})});
test('multi-file media sends one store envelope and preserves preview file-only writes',()=>{
 const {output}=build(),worker=output.find(w=>w.id==='snakeRetentionMediaV1');
 const records=[record('file:movie:1:2'),record('file:movie:1:3'),{key:'request:abc',kind:'subscription',payloadJson:'{}'}];
 const plan={owner:'12',mode:'preview',records};
 assert.deepEqual(run(worker,'Records To Persist',[plan]),[{json:{owner:'12',records:records.slice(0,2)}}]);
 assert.equal(worker.nodes.find(n=>n.name==='Persist Retention Records').parameters.mode,'once');
 assert.equal(worker.nodes.find(n=>n.name==='Persist Retention Records').parameters.options.waitForSubWorkflow,true);
 assert.deepEqual(run(worker,'Records To Persist',[{...plan,mode:'enabled'}]),[{json:{owner:'12',records:records.map(r=>({...r,owner:'12'}))}}]);
 assert.deepEqual(run(worker,'Records To Persist',[{...plan,records:[]}]),[{json:{skip:true}}]);
});
test('store validates every batch row before handing any records to native upsert',()=>{
 const {output}=build(),store=output.find(w=>w.id==='snakeRetentionStoreV1');
 const rows=[record('file:movie:1:2'),record('file:movie:1:3')],lock=[{key:'global',owner:'12'}];
 const execute=records=>run(store,'Validate Store Owner',lock,{'Record Input':{owner:'12',records}});
 assert.deepEqual(execute(rows),rows.map(json=>({json})));
 for(const bad of [record('file:movie:1:3','13'),{...rows[1],payloadJson:'invalid'},{...rows[1],kind:''},{...rows[1],key:''}])assert.throws(()=>execute([rows[0],bad]));
 assert.throws(()=>execute([rows[0],rows[0]]));
 assert.throws(()=>execute([]));
 for(const lock of [[],[{key:'global',owner:''}],[{key:'global',owner:'13'}],[{key:'global',owner:'12'},{key:'global',owner:'12'}]])
  assert.throws(()=>run(store,'Validate Store Owner',lock,{'Record Input':{owner:'12',records:rows}}));
 assert.deepEqual(run(store,'Validate Store Owner',[{key:'global',owner:'12'}],{'Record Input':rows[0]}),[{json:rows[0]}]);
});
test('overlay preserves native bindings, store graph, deletion nodes and workflow settings',()=>{
 const {source,output}=build();assert.equal(output.length,2);
 for(const before of source){
  const after=output.find(w=>w.id===before.id);
  assert.deepEqual(after.settings,before.settings);
  for(const node of before.nodes)if(!['Records To Persist','Has Retention Record?','Persist Retention Records','Validate Store Owner'].includes(node.name))
   assert.deepEqual(after.nodes.find(n=>n.name===node.name),node);
  assert.deepEqual(after.connections,before.connections);
 }
});
test('unsupported persistence shapes fail before generator writes files',()=>{
 const {source}=build(),{overlay}=require(script);
 for(const [name,field,value] of [['Read Store Lock','operation','insert'],['Upsert Retention Record','operation','update']]){
  const changed=structuredClone(source);
  changed.find(w=>w.id==='snakeRetentionStoreV1').nodes.find(n=>n.name===name).parameters[field]=value;
  assert.throws(()=>overlay(changed));
 }
 const changed=structuredClone(source);
 changed.find(w=>w.id==='snakeRetentionMediaV1').nodes.find(n=>n.name==='Persist Retention Records').onError='continueRegularOutput';
 assert.throws(()=>overlay(changed));
 assert.throws(()=>overlay(source.slice(0,1)));
 assert.throws(()=>overlay([...source,source[0]]));
 for(const name of ['Persist Retention Records','Validate Store Owner','Read Store Lock','Upsert Retention Record'])for(const field of ['continueOnFail','disabled']){
  const changed=structuredClone(source),w=changed.find(w=>w.nodes.some(n=>n.name===name));
  w.nodes.find(n=>n.name===name)[field]=true;
  assert.throws(()=>overlay(changed));
 }
 const guard=structuredClone(source);guard.find(w=>w.id==='snakeRetentionStoreV1').nodes.find(n=>n.name==='Validate Store Owner').onError='continueRegularOutput';
 assert.throws(()=>overlay(guard));
});
test('fresh export generation preserves bindings and credentials and leaves source untouched',()=>{
 const {source}=build(),{generate}=require(script),dir=fs.mkdtempSync(path.join(os.tmpdir(),'snake-batch-cli-'));
 try{
  const file=path.join(dir,'private.json'),out=path.join(dir,'out'),text=JSON.stringify(source);
  fs.writeFileSync(file,'\uFEFF'+text);assert.equal(generate(file,out),2);
  assert.equal(fs.readFileSync(file,'utf8'),'\uFEFF'+text);
  const store=JSON.parse(fs.readFileSync(path.join(out,'Snake Media - Store Retention Record.json')));
  assert.equal(store.nodes.find(n=>n.name==='Upsert Retention Record').parameters.dataTableId.value,'live-records');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
