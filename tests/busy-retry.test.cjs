const {test}=require('node:test'),a=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {transition}=require('../n8n/confirmation/policy.js');
const filename=path.join(__dirname,'../n8n/retry-fixes/workflows/Snake Media - Confirm Media.json');
test('busy backend restores exact prior confirmation with guarded native update',()=>{
 const w=JSON.parse(fs.readFileSync(filename,'utf8')),get=n=>w.nodes.find(x=>x.name===n);
 for(const origin of ['Commit Confirmed Media','Apply Retention Choice'])a.equal(w.connections[origin].main[0][0].node,'Backend Busy?');
 const restore=get('Restore Busy Choice').parameters;
 a.deepEqual(restore.filters.conditions.map(c=>c.keyName),['id','state','claimId']);
 a.equal(restore.filters.conditions[1].keyValue,'processing');
 a.match(restore.filters.conditions[2].keyValue,/execution.id/);
 const actor={source:'discord',userId:'2',destinationId:'3',action:'confirm'};
 for(const state of ['preview','scope','seasons']){
  const row={...actor,id:12,state,claimId:'old',choice:'choose',mediaType:state==='preview'?'movie':'tv',expiresAt:new Date(Date.now()+60000).toISOString()};
  const $=()=>({first:()=>({json:{row}})});
  const values=Object.fromEntries(Object.entries(restore.columns.value).map(([k,v])=>[k,new Function('$','return ('+v.slice(3,-2)+');')($)]));
  a.equal(values.state,state);a.equal(values.claimId,'old');a.equal(values.choice,'choose');
  const reply=new Function('$','$json',get('Busy Retry Reply').parameters.jsCode)($,{...row,...values})[0].json;
  a.equal(reply.actionAccepted,false);a.match(reply.text,/again/);
  a.equal(transition({...row,...values},{...actor,action:state==='seasons'?'season_1':state==='scope'?'latest':'confirm'},Date.now()),'processing');
  a.throws(()=>new Function('$','$json',get('Busy Retry Reply').parameters.jsCode)($,{...row,claimId:'another-execution'}));
 }
 const mark=get('Mark Accepted Action').parameters.jsCode;
 const $=name=>({first:()=>({json:name==='Validate Action'?{row:{}}:{actionAccepted:true}})});
 a.equal(new Function('$','$json',mark)($,{busy:true})[0].json.actionAccepted,false);
 a.equal(new Function('$','$json',mark)($,{status:'notice'})[0].json.actionAccepted,true);
});
