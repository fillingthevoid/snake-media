const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const rows=JSON.parse(fs.readFileSync(__dirname+'/../config-templates/n8n-current-media-workflows.json','utf8'));
const worker=rows.find(w=>w.id==='snakeRetentionMediaV1');
const nodes=Object.fromEntries(worker.nodes.map(n=>[n.name,n]));
function run(name,json){
 return JSON.parse(JSON.stringify(vm.runInNewContext('(function(){'+nodes[name].parameters.jsCode+'})()',{
  $json:json,$:()=>({first:()=>({json:{requests:[{mediaType:'tv',mediaId:'6'}],mode:'enabled'}})}),console:{warn:()=>{}},Date
 })));
}
test('failed snapshot reads can only reach a deferred summary before any mutations',()=>{
 for(const name of ['Read Retention Movie','Read Retention Series','Read Retention Episodes']){
  assert.equal(nodes[name].onError,'continueErrorOutput');
  assert.deepEqual(worker.connections[name].main[1],[{node:'Media Read Unavailable',type:'main',index:0}]);
 }
 assert.equal(worker.connections['Media Read Unavailable'],undefined);
 const result=run('Media Read Unavailable',{error:{message:'private upstream message'}})[0].json;
 assert.equal(result.snapshotUnavailable,true);assert.deepEqual(result.decisions,[]);
 assert.equal(result.alreadyRemoved,undefined);assert.equal(result.mediaId,'6');
 assert.equal(JSON.stringify(result).includes('private upstream'),false);
 for(const n of worker.nodes.filter(n=>n.type==='n8n-nodes-base.httpRequest'&&n.parameters.method&&n.parameters.method!=='GET')){
  assert.equal(n.onError,undefined);
 }
});
test('unavailable HTTP snapshots are deferred while 404 remains removed and valid media is retained',()=>{
 for(const name of ['Movie Snapshot Response','Series Snapshot Response']){
  for(const statusCode of [401,500,undefined])assert.equal(run(name,{statusCode})[0].json.unavailable,true);
  for(const body of [undefined,{}, {id:'6'}, {id:-1}])assert.equal(run(name,{statusCode:200,body})[0].json.unavailable,true);
  assert.equal(run(name,{statusCode:200,body:{id:6}})[0].json.id,6);
  assert.equal(run(name,{statusCode:404})[0].json.gone,true);
 }
 const result=run('Media Already Removed',{unavailable:true})[0].json;
 assert.equal(result.snapshotUnavailable,true);assert.equal(result.alreadyRemoved,undefined);
});
