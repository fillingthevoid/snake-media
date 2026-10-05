const {test}=require('node:test'),a=require('node:assert/strict');
const p=require('../n8n/efficiency-pass/policy.js');
const fs=require('node:fs'),vm=require('node:vm');
const bundle=JSON.parse(fs.readFileSync(__dirname+'/../config-templates/n8n-current-media-workflows.json'));
function execute(wid,start,input,refs,io){
 const w=bundle.find(w=>w.id===wid),saved={...refs};let name=start,steps=0;
 while(name){
  if(++steps>60)throw new Error('Unexpected graph loop');
  const n=w.nodes.find(n=>n.name===name);let branch=0;
  const $=key=>({first:()=>saved[key][0],all:()=>saved[key]});
  const context={$,$json:input[0]?.json,$input:{all:()=>input,first:()=>input[0]},Date};
  if(n.type.endsWith('.code'))input=vm.runInNewContext('(function(){'+n.parameters.jsCode+'})()',context);
  else if(n.type.endsWith('.if')){
   const expr=n.parameters.conditions.conditions[0].leftValue.slice(3,-2);
   branch=vm.runInNewContext(expr,context)?0:1;
  }else if(n.type.endsWith('.httpRequest'))input=io(n,input,context).map(json=>({json}));
  else if(n.type.endsWith('.executeWorkflow')){
   const child=n.parameters.workflowId.value;
   input=input.flatMap(i=>execute(child,bundle.find(w=>w.id===child).nodes[0].name,[i],{},io));
  }else if(n.type.endsWith('.dataTable'))return input; // Stop before final notice lookup.
  else if(!n.type.endsWith('.executeWorkflowTrigger'))throw new Error('Unexpected fixture node '+n.type);
  saved[name]=input;
  const next=w.connections[name]?.main?.[branch]||[];
  a.ok(next.length<=1,'fixture exercises serial status branches');
  name=next[0]?.node;
 }
 return JSON.parse(JSON.stringify(input));
}
test('queue snapshot rejects truncated pages and deduplicates stable IDs',()=>{
 a.throws(()=>p.queueRows([{records:[{id:1}],totalRecords:2}]),/Incomplete/);
 a.deepEqual(p.queueRows([{records:[{id:1},{id:2}],totalRecords:2}]),[{id:1},{id:2}]);
 a.throws(()=>p.queueRows([{records:null,totalRecords:0}]),/Incomplete/);
});
test('completion notice batches never issue an empty unscoped query',()=>{
 a.deepEqual(p.completionBatches([{}, {requestKey:'x',state:'registered',baselineCaptured:true,userId:'1',source:'discord'}]),[]);
 const r={requestKey:'discord:2:3',state:'registered',baselineCaptured:true,userId:'2',source:'discord'};
 a.deepEqual(p.completionBatches([r,r]),[{keys:['discord:2:3']}]);
 const batches=p.completionBatches(Array.from({length:401},(_,i)=>({...r,requestKey:'r'+i})));
 a.deepEqual(batches.map(b=>b.keys.length),[200,200,1]);
});
test('native fixed query rows resolve only keys in the current nonempty batch',()=>{
 const scan=bundle.find(w=>w.id==='snakeCompletionScanV1');
 const n=scan.nodes.find(n=>n.name==='Completion Notices');
 const keys=['a','b','c'];
 const values=n.parameters.filters.conditions.map(f=>{
  a.equal(f.keyName,'requestKey');a.equal(f.condition,'eq');
  return vm.runInNewContext(f.keyValue.slice(3,-2),{$json:{keys}});
 });
 const notices=[{requestKey:'a'},{requestKey:'b'},{requestKey:'c'},{requestKey:'other'}];
 a.deepEqual(notices.filter(n=>values.includes(n.requestKey)),notices.slice(0,3));
 a.ok(values.every(v=>keys.includes(v)));
});
test('watched snapshots keep exact retention fields while dropping bulky metadata',()=>{
 const row={Id:'a',Path:'/data/tv/x.mkv',ParentIndexNumber:1,IndexNumber:2,IndexNumberEnd:3,
  UserData:{Played:true,LastPlayedDate:'2026-10-05T00:00:00Z',PlayCount:4},Overview:'large',Images:['private']};
 a.deepEqual(p.compactWatched([{Items:[row],TotalRecordCount:1}]),[{Id:'a',Path:'/data/tv/x.mkv',ParentIndexNumber:1,IndexNumber:2,IndexNumberEnd:3,UserData:{Played:true,LastPlayedDate:'2026-10-05T00:00:00Z'}}]);
 a.throws(()=>p.compactWatched([{Items:[],TotalRecordCount:1}]),/Incomplete/);
 a.throws(()=>p.compactWatched([{Items:[{Id:'x'}],TotalRecordCount:1}]),/Invalid/);
});
test('mixed status shares each queue once and verifies only selected exact directories',()=>{
 const requests=[{requestKey:'a',source:'discord',userId:'2',state:'registered',mediaType:'movie',mediaId:'8',title:'A',retentionDays:7,episodeIdsJson:'[]'},
  {requestKey:'b',source:'discord',userId:'2',state:'registered',mediaType:'movie',mediaId:'9',title:'B',retentionDays:7,episodeIdsJson:'[]'},
  {requestKey:'c',source:'discord',userId:'2',state:'registered',mediaType:'tv',mediaId:'10',title:'C',retentionDays:30,episodeIdsJson:'["1"]'}];
 const refs={'Select Status Requests':[{json:{selected:requests.map(r=>({requests:[r]}))}}]},counts={};
 const io=(n,input,context)=>{
  counts[n.name]=(counts[n.name]||0)+1;
  if(n.name==='Read Shared Movie Queue'||n.name==='Read Shared TV Queue')return [{records:[],totalRecords:0}];
  if(n.name==='Read Status Movie'||n.name==='Read Status Series'){
   const r=context.$('Inspect Status Input').first().json.requests[0];
   return [{statusCode:200,body:{id:Number(r.mediaId),title:r.title,path:(r.mediaType==='movie'?'/movies/':'/tv/')+r.title,
    movieFile:r.mediaType==='movie'?{id:Number(r.mediaId)+100,path:'/movies/'+r.title+'/a.mkv',dateAdded:'2026-10-05T00:00:00Z'}:undefined}}];
  }
  if(n.name==='Read Status Episodes')return [{id:1,seasonNumber:1,episodeNumber:1,episodeFile:{id:110,path:'/tv/C/a.mkv',dateAdded:'2026-10-05T00:00:00Z'}}];
  if(n.name==='Read Target Movies'){
   const t=context.$('Target Input').first().json;
   return [{Items:[{Id:t.title,Path:'/data'+t.mediaPath+'/a.mkv'},{Id:'wrong',Path:'/data/movies/Other/a.mkv'}],TotalRecordCount:2}];
  }
  if(n.name==='Read Target Series')return [{Items:[{Id:'series',Path:'/data/tv/C'}],TotalRecordCount:1}];
  if(n.name==='Read Series Files')return [{Items:[{Id:'episode',Path:'/data/tv/C/a.mkv'}],TotalRecordCount:1}];
  throw new Error('Unexpected HTTP read '+n.name);
 };
 const out=execute('snakeStatusV1','Status Queue Context',[{json:{}}],refs,io);
 a.equal(out.length,3);for(const item of out)a.match(item.json.text,/Available in Jellyfin|available in Jellyfin/);
 a.equal(counts['Read Shared Movie Queue'],1);a.equal(counts['Read Shared TV Queue'],1);
 a.equal(counts['Read Target Movies'],2);a.equal(counts['Read Target Series'],1);
 a.equal(counts['Read Status Movie Queue'],undefined);a.equal(counts['Read Status TV Queue'],undefined);
});
test('movie-only status skips Sonarr and missing media skips Jellyfin target reads',()=>{
 const r={requestKey:'a',mediaType:'movie',mediaId:'8',title:'A',retentionDays:7,episodeIdsJson:'[]'};
 const refs={'Select Status Requests':[{json:{selected:[{requests:[r]}]}}]},counts={};
 const io=n=>{
  counts[n.name]=(counts[n.name]||0)+1;
  if(n.name==='Read Shared Movie Queue')return [{records:[],totalRecords:0}];
  if(n.name==='Read Status Movie')return [{statusCode:404,body:{}}];
  throw new Error('Unexpected read '+n.name);
 };
 const out=execute('snakeStatusV1','Status Queue Context',[{json:{}}],refs,io);
 a.match(out[0].json.text,/No longer listed in Radarr/);
 a.deepEqual(counts,{'Read Shared Movie Queue':1,'Read Status Movie':1});
});
test('progress inspectors without a shared snapshot retain their own queue read',()=>{
 const input={requests:[{mediaType:'movie',mediaId:'8',title:'A',episodeIdsJson:'[]',retentionDays:7}],records:[]};
 const counts={};const io=n=>{
  counts[n.name]=(counts[n.name]||0)+1;
  if(n.name==='Read Status Movie')return [{statusCode:404,body:{}}];
  if(n.name==='Read Status Movie Queue')return [{records:[],totalRecords:0}];
  throw new Error('Unexpected HTTP '+n.name);
 };
 const out=execute('snakeStatusInspectV1','Inspect Status Input',[{json:input}],{},io);
 a.match(out[0].json.text,/No longer listed/);
 a.deepEqual(counts,{'Read Status Movie':1,'Read Status Movie Queue':1});
});
test('compaction preserves expiry, multi-episode and playback safety decisions',()=>{
 const module={exports:{}};
 for(const file of ['policy.js','engine.js'])vm.runInNewContext(fs.readFileSync(__dirname+'/../n8n/retention/'+file,'utf8'),{module,Date,...module.exports});
 const date=n=>new Date(Date.UTC(2026,0,1+n)).toISOString();
 const r={requestKey:'discord:2:3',mediaType:'tv',mediaId:'2',title:'Show',requestedAt:date(0),baselineCaptured:true,retentionDays:30,episodeIdsJson:'["10","11"]',preexistingFileIdsJson:'[]'};
 const watched=[{Id:'j',Path:'/data/tv/Show/a.mkv',ParentIndexNumber:1,IndexNumber:1,IndexNumberEnd:2,UserData:{Played:true,LastPlayedDate:date(4)},Overview:'large'.repeat(1000)}];
 const input={now:Date.parse(date(12)),requests:[r],records:[{key:'request:'+r.requestKey,kind:'subscription',payloadJson:JSON.stringify({requestKey:r.requestKey,mediaType:'tv',mediaId:'2',historicalSeasons:[1],selectedSeasons:[1],episodeIds:['10','11']})}],media:{id:2},episodes:[1,2].map((ep,i)=>({id:10+i,seasonNumber:1,episodeNumber:ep,episodeFileId:100,airDateUtc:date(0),episodeFile:{id:100,path:'/tv/Show/a.mkv',dateAdded:date(1)}})),watched,sessions:[]};
 const compact=p.compactWatched([{Items:watched,TotalRecordCount:1}]);
 for(const sessions of [[],[{NowPlayingItem:{Id:'j'}}],[{NowPlayingItem:{Id:'unknown'}}]]){
  const original=module.exports.planMedia({...input,sessions});
  const reduced=module.exports.planMedia({...input,sessions,watched:compact});
  a.equal(JSON.stringify(reduced),JSON.stringify(original));
 }
 a.ok(JSON.stringify(compact).length<JSON.stringify(watched).length/10);
});
test('all current Code nodes compile without credentials or live services',()=>{
 for(const w of bundle)for(const n of w.nodes)if(n.type.endsWith('.code'))new Function(n.parameters.jsCode);
});
