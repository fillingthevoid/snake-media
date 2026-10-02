const {test}=require('node:test'),a=require('node:assert/strict');
const p=require('../n8n/status/policy.js');
const now=Date.parse('2026-10-01T12:00:00Z');
const r={source:'discord',userId:'2',requestKey:'d:2:3',state:'registered',title:'Example',mediaType:'movie',mediaId:'8',requestedAt:'2026-09-30',episodeIdsJson:'[]'};
test('status routing is explicit, bounded, and does not consume add commands',()=>{
 a.equal(p.command('add status quo'),null);a.equal(p.command('/status@snake_bot Example'),'Example');a.equal(p.command('status'),'');
 a.equal(p.command('statusExample'),null);
});
test('selection protects identities, excludes synthetic rows, and refuses ambiguous titles',()=>{
 a.equal(p.select([r,{...r,userId:'9',mediaId:'9'}],{source:'discord',userId:'2',query:''}).length,1);
 a.equal(p.select([r],{source:'telegram',userId:'2',query:''})[0].notice.includes('No requests'),true);
 a.match(p.select([r,{...r,title:'Example Two',mediaId:'9'}],{source:'discord',userId:'2',query:'Example'})[0].notice,/matches/);
});
test('availability requires exact Jellyfin path and expiry uses matching current file',()=>{
 const file={id:4,path:'/movies/x.mkv',dateAdded:'2026-09-30T12:00:00Z'};
 const ledger={key:'file:movie:8:4',payloadJson:JSON.stringify({fileId:4,path:file.path,importedAt:file.dateAdded,state:'tracked',expiresAt:'2026-10-07T12:00:00Z',checkedAt:new Date(now).toISOString(),reason:'retained'})};
 const input={requests:[r],records:[ledger],media:{id:8,movieFile:file},episodes:[],queue:[],library:[],now};
 a.match(p.describe(input),/Imported/);a.doesNotMatch(p.describe(input),/Available in Jellyfin/);
 input.library=[{Id:'x',Path:'/data/movies/x.mkv'}];a.match(p.describe(input),/Available in Jellyfin/);a.match(p.describe(input),/Oct 7/);
 input.media.movieFile={...file,id:5};a.match(p.describe(input),/pending/);
});
test('TV counts only selected episodes and reports protected files without a date',()=>{
 const request={...r,mediaType:'tv',episodeIdsJson:'["1","2"]'};
 const f={id:4,path:'/tv/x.mkv',dateAdded:'2026-09-30T12:00:00Z'};
 const records=[{key:'file:tv:8:4',payloadJson:JSON.stringify({fileId:4,path:f.path,importedAt:f.dateAdded,state:'tracked',expiresAt:null,checkedAt:new Date(now).toISOString(),reason:'protected claim'})}];
 const text=p.describe({requests:[request],records,media:{id:8},episodes:[{id:1,seasonNumber:1,episodeNumber:1,episodeFile:f,episodeFileId:4},{id:2,seasonNumber:1,episodeNumber:2,airDateUtc:'2099-01-01'},{id:3,seasonNumber:2,episodeNumber:1}],queue:[],library:[],now});
 a.match(text,/1 imported/);a.match(text,/1 awaiting release/);a.match(text,/1 protected/);a.doesNotMatch(text,/waiting for a release/);
});

test('generated status subworkflows contain only reads and keep authorization before routing',()=>{
 const fs=require('node:fs'),dir=__dirname+'/../n8n/status/workflows/';
 const ws=fs.readdirSync(dir).map(f=>JSON.parse(fs.readFileSync(dir+f)));
 for(const w of ws){
  const names=new Set(w.nodes.map(n=>n.name));
  for(const n of w.nodes)if(n.type.endsWith('.code'))new Function(n.parameters.jsCode);
  for(const c of Object.values(w.connections))for(const ports of Object.values(c))for(const es of ports)for(const e of es)a.ok(names.has(e.node));
  if(w.id.startsWith('snakeStatus'))for(const n of w.nodes){
   if(n.type.endsWith('.httpRequest'))a.equal(n.parameters.method,'GET');
   if(n.type.endsWith('.dataTable'))a.equal(n.parameters.operation,'get');
   a.ok(!n.type.endsWith('.webhook'));
  }
  else {
   a.equal(w.connections['Confirmation Callback?'].main[1][0].node,'Parse Status Command');
   const auth=w.name.endsWith('Discord')?'Authorized Request?':'Authorized User?';
   a.equal(w.connections[auth].main[0][0].node,'Confirmation Callback?');
   a.equal(w.connections['Status Command?'].main[1][0].node,'Interpret Media Request');
  }
 }
});
test('stale expiry is labelled and deleted/replaced identities cannot show an old deadline',()=>{
 const f={id:4,path:'/movies/x.mkv',dateAdded:'2026-09-30T12:00:00Z'};
 const v={fileId:4,path:f.path,importedAt:f.dateAdded,state:'tracked',expiresAt:'2026-10-07T12:00:00Z',checkedAt:'2026-09-30T12:00:00Z',reason:'retained'};
 const input={requests:[r],records:[{key:'file:movie:8:4',payloadJson:JSON.stringify(v)}],media:{id:8,movieFile:f},episodes:[],queue:[],library:[],now};
 a.match(p.describe(input),/stale/);
 input.records[0].payloadJson=JSON.stringify({...v,state:'deleted'});a.match(p.describe(input),/pending/);a.doesNotMatch(p.describe(input),/Oct 7/);
});

test('permanent amendments are visible before a file imports',()=>{
 const input={requests:[{...r,retentionDays:7}],records:[{key:'change:1',payloadJson:JSON.stringify({version:1,operation:'permanent',mediaType:'movie',mediaId:'8',requestKeys:[r.requestKey]})}],media:{id:8},episodes:[],queue:[],library:[],now};
 a.match(p.describe(input),/Permanent/);
});
