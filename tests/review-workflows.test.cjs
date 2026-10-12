const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const bundle=JSON.parse(fs.readFileSync(__dirname+'/../config-templates/n8n-current-media-workflows.json'));

// Execute the maintained movie branch; external HTTP/table boundaries are local fakes.
function requestMovie({available=false,verification='ok'}={}){
 const w=bundle.find(w=>w.id==='snakeCommitUnderLockV1'||w.name==='Snake Media - Commit Media Under Lock');
 const nodes=Object.fromEntries(w.nodes.map(n=>[n.name,n])),calls=[],saved={};
 const movie={id:9,tmdbId:99,title:'Example',monitored:false,...(available?{movieFile:{id:10}}:{})};
 const context={source:'discord',userId:'2',destinationId:'3',messageId:'4',retentionPolicy:{days:7}};
 const refs={'Confirmed Metadata':[{json:{media:{tmdbId:99},context}}],'Commit Input':[{json:{owner:'12',id:1,claimId:'12'}}]};
 let rows=[{json:movie}],name='Existing Movie',reply,error;
 for(let count=0;name&&count<40;count++){
  const n=nodes[name],p=n.parameters;assert.ok(n,'unknown node '+name);
  const env={$json:rows[0]?.json,$input:{first:()=>rows[0],all:()=>rows},$:key=>({first:()=>refs[key][0],all:()=>refs[key]}),Date};
  const evaluate=value=>vm.runInNewContext('('+value.replace(/^=\{\{\s*/,'').replace(/\s*\}\}$/,'')+')',env);
  let port=0;
  try{
   if(n.type.endsWith('.code'))rows=vm.runInNewContext('(function(){'+p.jsCode+'})()',env);
   else if(n.type.endsWith('.if'))port=evaluate(p.conditions.conditions[0].leftValue)?0:1;
   else if(n.type.endsWith('.executeWorkflow')){
    const input=rows[0].json;
    if(name==='Register Movie Before Search'){saved.tracking=input;rows=[{json:{...input,requestKey:'discord:3:4'}}];}
    else if(name==='Save Movie Subscription'){saved.subscription=input;rows=[{json:{key:input.key}}];}
    else throw Error('Unexpected child '+name);
   }else if(n.type.endsWith('.httpRequest')){
    const body=p.jsonBody?evaluate(p.jsonBody):null;
    calls.push({name,method:p.method,body:body&&JSON.parse(JSON.stringify(body))});
    if(p.method==='PUT'){
     assert.ok(saved.tracking&&saved.subscription,'monitoring must follow durable ownership tracking');
     assert.deepEqual(JSON.parse(JSON.stringify(body)),{movieIds:[9],monitored:true});
     if(verification==='put-error')throw Error('monitoring service unavailable');
     movie.monitored=true;rows=[{json:{...movie}}];
    }else if(p.method==='GET'){
     if(verification==='get-error')throw Error('verification unavailable');
     rows=[{json:{...movie,monitored:verification==='unmonitored'?false:movie.monitored,id:verification==='wrong-id'?10:9,tmdbId:verification==='wrong-external-id'?100:99}}];
    }else{
     assert.equal(body.name,'MoviesSearch');assert.deepEqual(Array.from(body.movieIds),[9]);
     rows=[{json:{id:123,status:'queued'}}];
    }
   }else if(n.type.endsWith('.dataTable'))rows=[{json:{state:'done'}}];
   else throw Error('Unexpected node type '+n.type);
   refs[name]=rows;
  }catch(e){error=e;break;}
  if(name==='Return Outcome')reply=rows[0].json;
  name=w.connections[name]?.main?.[port]?.[0]?.node;
 }
 return {movie,calls,reply,error};
}

test('requesting a previously expired movie restores monitoring before its search',()=>{
 const r=requestMovie();assert.ifError(r.error);assert.equal(r.movie.monitored,true);
 assert.deepEqual(r.calls.map(c=>c.method),['PUT','GET','POST']);assert.match(r.reply.text,/Search started/);
});

test('available movies keep existing monitoring and skip both mutation and search',()=>{
 const r=requestMovie({available:true});assert.ifError(r.error);assert.equal(r.movie.monitored,false);
 assert.deepEqual(r.calls,[]);assert.match(r.reply.text,/Already imported/);
});

test('failed or mismatched monitoring verification cannot authorize a movie search',()=>{
 for(const verification of ['put-error','get-error','unmonitored','wrong-id','wrong-external-id']){
  const r=requestMovie({verification});assert.ok(r.error,'must reject '+verification);
  assert.equal(r.calls.some(c=>c.method==='POST'),false);
 }
});

test('embedded entry policies preserve title-free extension days on both platforms',()=>{
 for(const wid of ['HXtTzVTrpNZMZVt3','0e67KTcphqxEKNsh']){
  const w=bundle.find(w=>w.id===wid),body=w.nodes.find(n=>n.name==='Parse Retention Command').parameters.jsCode;
  const marker="if(typeof module!=='undefined')module.exports={parseChange,prepareChange,planChange,changeCard,guideAction,titleKey};";
  const out=vm.runInNewContext('(function(){'+body.slice(0,body.indexOf(marker))+'\nreturn parseChange("extend 30 days");})()');
  assert.deepEqual(JSON.parse(JSON.stringify(out)),{operation:'extend',guided:true,days:30});
 }
});
