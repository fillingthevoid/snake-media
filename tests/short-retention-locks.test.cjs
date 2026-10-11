const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const {freshGroup}=require('../n8n/retention-locks/policy.js');
const now=Date.parse('2026-10-10T21:00:00Z');
const request={requestKey:'discord:11:22',userId:'11',state:'registered',mediaType:'movie',mediaId:'2',requestedAt:'2026-09-01T00:00:00Z',baselineCaptured:true,retentionDays:7,episodeIdsJson:'[]',preexistingFileIdsJson:'[]'};
const input={owner:'50',requests:[request],records:[],watched:[],sessions:[],snapshotAt:new Date(now-1000).toISOString()};
test('fresh claims and amendments replace the earlier scan snapshot',()=>{
 const current=[{...request,retentionDays:30}],records=[{key:'change:3',kind:'amendment',payloadJson:'{}'}];
 const r=freshGroup(input,current,records,'preview',now);
 assert.equal(r.requests[0].retentionDays,30);assert.deepEqual(r.records,records);assert.equal(r.mode,'preview');assert.equal(input.requests[0].retentionDays,7);
});
test('stale or removed groups defer; identity and unknown mode fail closed',()=>{
 assert.equal(freshGroup({...input,snapshotAt:new Date(now-300001).toISOString()},[request],[],'enabled',now).deferred,true);
 assert.equal(freshGroup(input,[],[],'enabled',now).deferred,true);
 assert.equal(freshGroup(input,[{}],[{}],'enabled',now).deferred,true);
 for(const [i,rs,mode]of [[{...input,owner:''},[request],'enabled'],[input,[{...request,mediaId:'9'}],'enabled'],[input,[request],'unknown']])assert.throws(()=>freshGroup(i,rs,[],mode,now));
});
test('a permanent keep added since collection prevents deletion in the real planner',()=>{
 const m={exports:{}},ctx={module:m,Date};vm.runInNewContext(fs.readFileSync(__dirname+'/../n8n/retention/policy.js','utf8')+'\n'+fs.readFileSync(__dirname+'/../n8n/retention/engine.js','utf8'),ctx);
 const sub={key:'request:'+request.requestKey,payloadJson:JSON.stringify({requestKey:request.requestKey,mediaType:'movie',mediaId:'2',episodeIds:[],protectedFileIds:[]})};
 const media={id:2,movieFile:{id:4,path:'/movies/Test/Test.mkv',dateAdded:'2026-09-02T00:00:00Z'}};
 const base={...freshGroup(input,[request],[sub],'enabled',now),media,episodes:[],now};assert.equal(m.exports.planMedia(base).deletions.length,1);
 const keep={key:'change:5',payloadJson:JSON.stringify({version:1,mediaType:'movie',mediaId:'2',requestKeys:[request.requestKey],operation:'permanent'})};
 assert.equal(m.exports.planMedia({...base,...freshGroup(input,[request],[sub,keep],'enabled',now)}).deletions.length,0);
});
test('installed native failure gate permits only the exact preparing owner',()=>{
 const bundle=JSON.parse(fs.readFileSync(__dirname+'/../config-templates/n8n-current-media-workflows.json','utf8'));
 const coord=bundle.find(w=>w.id==='snakeRetentionCoordinatorV1'),nodes=Object.fromEntries(coord.nodes.map(n=>[n.name,n]));
 const expression=nodes['Safe Planning Failure?'].parameters.conditions.conditions[0].leftValue;
 const evaluate=(row,count=1)=>new Function('$json','$execution','$','return ('+expression.slice(3,-2)+')')(row,{id:'50'},()=>({all:()=>Array.from({length:count},()=>({json:row}))}));
 assert.equal(evaluate({key:'global-phase',owner:'50:preparing'}),true);
 for(const row of [{key:'global-phase',owner:'50:mutating'},{key:'global-phase',owner:'51:preparing'},{key:'global',owner:'50:preparing'},{}])assert.equal(evaluate(row),false);
 assert.equal(evaluate({key:'global-phase',owner:'50:preparing'},2),false);
 const filter=nodes['Release Safe Failed Lock'].parameters.filters.conditions.find(f=>f.keyName==='owner');
 const expected=new Function('$execution','return ('+filter.keyValue.slice(3,-2)+')')({id:'50'});
 assert.equal(expected,'50');assert.notEqual(expected,'51');
});

test('amendment previews preserve the existing mutating phase instead of requiring preparing again',()=>{
 const bundle=JSON.parse(fs.readFileSync(__dirname+'/../config-templates/n8n-current-media-workflows.json','utf8'));
 const workflow=id=>bundle.find(w=>w.id===id),node=(id,name)=>workflow(id).nodes.find(n=>n.name===name);
 const amend=node('snakeRetentionCoordinatorV1','Mark Other Mutation');
 const phase=new Function('$execution','return ('+amend.parameters.columns.value.owner.slice(3,-2)+')')({id:'50'});
 assert.equal(phase,'50:mutating');
 assert.equal(node('snakeRetentionChangeSnapshotV1','Process Each Retention Group').parameters.workflowId.value,'snakeRetentionMediaV1');
 const filter=node('snakeRetentionMediaV1','Mark Retention Mutation').parameters.filters.conditions.find(f=>f.keyName==='owner');
 const expected=input=>new Function('$','return ('+filter.keyValue.slice(3,-2)+')')(()=>({first:()=>({json:input})}));
 assert.equal(expected({owner:'50',mode:'preview'}),phase);
 assert.equal(expected({owner:'50',mode:'preview',job:'retention_media'}),'50:preparing');
 assert.notEqual(expected({owner:'51',mode:'preview'}),phase);
 assert.notEqual(expected({owner:'50',mode:'enabled'}),phase);
 const resulting=node('snakeRetentionMediaV1','Mark Retention Mutation').parameters.columns.value.owner;
 assert.equal(new Function('$','return ('+resulting.slice(3,-2)+')')(()=>({first:()=>({json:{owner:'50',mode:'preview'}})})),phase);
});
