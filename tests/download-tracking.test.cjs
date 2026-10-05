const {test}=require('node:test'),a=require('node:assert/strict');
const p=require('../n8n/download-tracking/policy.js');
const now=Date.parse('2026-10-05T12:05:00Z');
test('native imports track immutable IDs without saving release payloads or credentials',()=>{
 const body={eventType:'Download',series:{id:7,title:'Example'},episodes:[{id:11},{id:12}],
 episodeFile:{id:30},downloadId:'SABnzbd_nzo_123',release:{title:'private release'},headers:{Authorization:'secret'}};
 const r=p.normalizeEvent(body,'tv',now);
 a.ok(r,'import must produce a tracking record');
 a.equal(r.mediaId,'7');a.equal(r.fileId,'30');a.deepEqual(JSON.parse(r.episodeIdsJson),['11','12']);
 a.deepEqual(JSON.parse(r.payloadJson),{eventType:'Download',downloadId:'SABnzbd_nzo_123'});
 a.equal(r.eventKey,p.normalizeEvent(body,'tv',now+60000).eventKey);
 a.equal(r.state,'imported');
});
test('grab IDs correlate later imported movies and tests never create work',()=>{
 const grab=p.normalizeEvent({eventType:'Grab',movie:{id:8},downloadId:'abcdef1234'},'movie',now);
 a.ok(grab,'grab must produce a tracking record');
 a.equal(grab.state,'downloading');a.equal(grab.importedAt,null);
 a.equal(p.normalizeEvent({eventType:'Test'},'movie',now),null);
 for(const body of [{eventType:'Download',movie:{id:8}},
  {eventType:'Download',movie:{id:'8'},movieFile:{id:1}},
  {eventType:'Delete',movie:{id:8}},
  {eventType:'Grab',series:{id:8},episodes:[],downloadId:'abc'}])
  a.throws(()=>p.normalizeEvent(body,body.series?'tv':'movie',now));
});
test('events target matching requested episodes; old events fall back every fifteen minutes',()=>{
 const r={requestKey:'r',mediaType:'tv',mediaId:'7',episodeIdsJson:'["11"]',requestedAt:'2026-10-05T11:00:00Z'};
 const event={mediaType:'tv',mediaId:'7',state:'imported',episodeIdsJson:'["11"]',receivedAt:'2026-10-05T12:04:00Z'};
 a.deepEqual(p.affectedRequests([r],[event],now),[r]);
 for(const patch of [{mediaId:'9'},{episodeIdsJson:'["12"]'},{receivedAt:'2026-10-05T11:00:00Z'}])
  a.deepEqual(p.affectedRequests([r],[{...event,...patch}],now),[]);
 a.deepEqual(p.affectedRequests([r],[],Date.parse('2026-10-05T12:15:00Z')),[r]);
 a.deepEqual(p.affectedRequests([{...r,requestedAt:'2026-10-05T12:00:00Z'}],[],now).map(x=>x.requestKey),['r']);
});
test('targeted Jellyfin search verifies directory identity and refuses an ambiguous series root',()=>{
 const pages=[{Items:[{Id:'wrong',Path:'/data/tv/Other'},{Id:'right',Path:'/data/tv/Example'}],TotalRecordCount:2}];
 a.equal(p.targetRoot('tv','/tv/Example',pages),'right');
 a.equal(p.targetRoot('tv','/tv/Missing',pages),null);
 a.throws(()=>p.targetRoot('tv','/tv/Example',[{Items:[{Id:'a',Path:'/data/tv/Example'},{Id:'b',Path:'/data/tv/Example'}]}]));
 a.deepEqual(p.targetFiles('/tv/Example',[{Items:[{Id:'a',Path:'/data/tv/Example/S01/a.mkv'},{Id:'b',Path:'/data/tv/Example II/b.mkv'}],TotalRecordCount:2}]),
  [{Id:'a',Path:'/data/tv/Example/S01/a.mkv'}]);
 a.throws(()=>p.targetFiles('/tv/Example',[{Items:[{Id:'a',Path:'/data/tv/Example/a.mkv'}],TotalRecordCount:2}]));
 a.throws(()=>p.targetFiles('/tv/../Other',pages));
});
test('current completion graph uses authenticated events and targeted queries for both front ends',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const bundle=JSON.parse(fs.readFileSync(path.join(__dirname,'../config-templates/n8n-current-media-workflows.json'),'utf8'));
 const byId=id=>bundle.find(w=>w.id===id);
 const target=byId('snakeTargetLibraryV1');a.ok(target,'targeted helper must exist');
 const scan=byId('snakeCompletionScanV1');
 a.ok(!scan.nodes.some(n=>n.name==='Read Jellyfin Library'));
 a.equal(scan.nodes.find(n=>n.name==='Prune Old Download Events').parameters.operation,'deleteRows',
  'event pruning must use the native Data Table deletion operation');
 for(const kind of ['Sonarr','Radarr']){
  const w=byId('snake'+kind+'EventsV1');a.ok(w);
  const webhook=w.nodes.find(n=>n.type.endsWith('.webhook'));
  a.equal(webhook.parameters.authentication,'headerAuth');a.ok(webhook.credentials);
  const storage=w.nodes.find(n=>n.name==='Store Download Event');a.equal(storage.parameters.operation,'upsert');
 }
 for(const w of [target,scan,byId('snakeInspectRequestV1')]){
  const names=new Set(w.nodes.map(n=>n.name));
  for(const [name,ports] of Object.entries(w.connections)){
   a.ok(names.has(name));for(const rows of Object.values(ports))for(const row of rows)for(const edge of row)a.ok(names.has(edge.node));
  }
  for(const n of w.nodes)if(n.type.endsWith('.code'))new Function('$','$input','$json',n.parameters.jsCode);
 }
 const fields=target.nodes.find(n=>n.name==='Read Series Files').parameters.queryParameters.parameters;
 a.ok(fields.some(f=>f.name==='ParentId'&&f.value.includes('$json.parentId')));
});
