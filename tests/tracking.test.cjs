const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function run(file, input, refs={}) {
  const script = fs.readFileSync(path.join(__dirname,'../n8n/tracking/code',file),'utf8');
  return JSON.parse(JSON.stringify(vm.runInNewContext(`(function(){${script}\n})()`,{
    $input:{first:()=>({json:input}),all:()=>input.map(x=>({json:x}))},
    $:name=>({first:()=>({json:refs[name]})}),
  },{timeout:1000})));
}
const request = {source:'discord',userId:'100000000000000001',destinationId:'100000000000000004',
  messageId:'1554335649610334229',requestedAt:'2026-09-29T00:00:00.000Z',text:'add Matrix',
  mediaType:'movie',mediaId:'12',externalId:'603',title:'The Matrix',
  episodeIds:[],preexistingFileIds:[],baselineCaptured:true};
test('normalizes identity and permanent default without losing snowflake precision',()=>{
  const out=run('normalize-request.js',request)[0].json;
  assert.equal(out.requestKey,'discord:100000000000000004:1554335649610334229');
  assert.equal(out.userId,'100000000000000001');
  assert.equal(out.retentionDays,null);
  assert.equal(out.deletionEligible,false);
});
test('Telegram supports negative group chat IDs and independently keyed messages',()=>{
  const out=run('normalize-request.js',{...request,source:'telegram',destinationId:'-1001234567890',messageId:'123'})[0].json;
  assert.equal(out.requestKey,'telegram:-1001234567890:123');
});
test('only explicit validated retention and known baseline can become eligible',()=>{
  const out=run('normalize-request.js',{...request,retentionDays:14,retentionExplicit:true})[0].json;
  assert.equal(out.retentionDays,14); assert.equal(out.deletionEligible,true);
  const unknown=run('normalize-request.js',{...request,baselineCaptured:false,retentionDays:14,retentionExplicit:true})[0].json;
  assert.equal(unknown.deletionEligible,false);
  for(const retentionDays of [0,-1,1.5,'14',3651]) assert.throws(()=>run('normalize-request.js',{...request,retentionDays,retentionExplicit:true}));
  assert.throws(()=>run('normalize-request.js',{...request,retentionDays:14}));
});
test('TV scope is an explicit episode set; existing file IDs are retained',()=>{
  const out=run('normalize-request.js',{...request,mediaType:'tv',episodeIds:['8','7','8'],preexistingFileIds:['44']})[0].json;
  assert.equal(out.episodeIdsJson,'["7","8"]');
  assert.equal(out.preexistingFileIdsJson,'["44"]');
  assert.throws(()=>run('normalize-request.js',{...request,mediaType:'tv'}));
  assert.throws(()=>run('normalize-request.js',{...request,episodeIds:['7']}));
});
test('rejects invalid sources, numeric platform IDs and invalid timestamps',()=>{
  for (const change of [{source:'other'},{userId:100000000000000001},{destinationId:'1:2'},
    {messageId:''},{requestedAt:'yesterday'},{requestedAt:'2026-02-30T00:00:00.000Z'},
    {mediaId:'0'},{title:''},{baselineCaptured:'true'},{preexistingFileIds:['path/to/file']}]) {
    assert.throws(()=>run('normalize-request.js',{...request,...change}));
  }
});
test('same request retries preserve the stored row; conflicting reuse and duplicates fail',()=>{
  const normalized=run('normalize-request.js',request)[0].json;
  const existing={...normalized,id:1,createdAt:'2026-09-29T00:00:00.000Z',updatedAt:'2026-09-29T00:00:00.000Z'};
  const refs={'Normalize Request':normalized};
  assert.equal(run('resolve-existing.js',[existing],refs)[0].json.exists,true);
  assert.equal(run('resolve-existing.js',[{}],refs)[0].json.exists,false);
  assert.throws(()=>run('resolve-existing.js',[{...existing,retentionDays:14}],refs));
  assert.throws(()=>run('resolve-existing.js',[existing,existing],refs));
});
