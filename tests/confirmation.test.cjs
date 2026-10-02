const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const file=__dirname+'/../n8n/confirmation/policy.js';
function policy(){const module={exports:{}};if(fs.existsSync(file))vm.runInNewContext(fs.readFileSync(file,'utf8'),{module,Date});return module.exports;}
test('aired scope excludes specials and future and latest uses last aired season',()=>{
 const p=policy();assert.equal(typeof p.scope,'function');
 const e=[{id:1,seasonNumber:0,airDateUtc:'2020-01-01'},{id:2,seasonNumber:1,airDateUtc:'2020-01-01'},{id:3,seasonNumber:2,airDateUtc:'2025-01-01',episodeFileId:12},{id:4,seasonNumber:3,airDateUtc:'2099-01-01'}];
 assert.equal(JSON.stringify(p.scope(e,'latest',Date.parse('2026-01-01'))),JSON.stringify([e[2]]));
 assert.equal(p.scope(e,'all',Date.parse('2026-01-01')).length,2);
 assert.equal(p.scope(e,'season_1',Date.parse('2026-01-01'))[0].id,2);
 assert.throws(()=>p.scope(e,'season_0',Date.now()));
});
test('pending state binds actor, destination and expiry and rejects replays',()=>{
 const p=policy();assert.equal(typeof p.transition,'function');
 const r={source:'discord',userId:'111',destinationId:'333',state:'preview',mediaType:'tv',expiresAt:'2099-01-01'};
 const a={source:'discord',userId:'111',destinationId:'333',action:'confirm'};
 assert.equal(p.transition(r,a,Date.now()),'scope');
 assert.throws(()=>p.transition(r,{...a,userId:'222'},Date.now()));
 assert.throws(()=>p.transition(r,{...a,destinationId:'444'},Date.now()));
 assert.throws(()=>p.transition({...r,expiresAt:'2000-01-01'},a,Date.now()));
 assert.throws(()=>p.transition({...r,state:'processing'},a,Date.now()));
 assert.equal(p.transition(r,{...a,action:'cancel'},Date.now()),'cancelled');
 assert.equal(p.transition({...r,mediaType:'movie'},a,Date.now()),'processing');
 assert.throws(()=>p.transition(r,{...a,action:'latest'},Date.now()));
});

test('season paging stays in selection and cannot bypass confirmation',()=>{
 const p=policy(),r={source:'discord',userId:'111',destinationId:'333',state:'seasons',mediaType:'tv',expiresAt:'2099-01-01'};
 assert.equal(p.transition(r,{source:'discord',userId:'111',destinationId:'333',action:'page_1'},Date.now()),'seasons');
});

test('initial requests reach only read-only preview, commit tracks before search',()=>{
 const dir=__dirname+'/../n8n/confirmation/workflows/';
 for(const platform of ['Discord','Telegram']){
  const w=JSON.parse(fs.readFileSync(dir+'Media Request - '+platform+'.json'));
  assert.equal(w.nodes.some(n=>['Add Movie - Radarr','Add TV Show - Sonarr'].includes(n.name)),false);
  assert.ok(w.nodes.some(n=>n.name==='Resolve Confirmation'));
 }
 const w=JSON.parse(fs.readFileSync(dir+'Snake Media - Preview Media.json'));
 assert.ok(w.nodes.filter(n=>n.type.endsWith('.httpRequest')).every(n=>n.parameters.method==='GET'));
 const c=JSON.parse(fs.readFileSync(dir+'Snake Media - Commit Confirmed Media.json'));
 const series=c.nodes.find(n=>n.name==='Build Series Payload').parameters.jsCode;
 assert.match(series,/searchForMissingEpisodes:false/);assert.match(series,/monitored:false/);
 assert.ok(c.connections['Register TV Before Search']);
 // All generated scripts must parse before import.
 for(const file of fs.readdirSync(dir))for(const node of JSON.parse(fs.readFileSync(dir+file)).nodes){
  if(node.type.endsWith('.code'))new Function(node.parameters.jsCode);
 }
});

test('new media payloads disable implicit searches and future series monitoring',()=>{
 const path=__dirname+'/../n8n/confirmation/add-payload.js';
 assert.ok(fs.existsSync(path),'new-title payload builder exists');
 const script=fs.readFileSync(path,'utf8');
 function build(mediaType){return JSON.parse(JSON.stringify(vm.runInNewContext('(function(){'+script+'})()',{$:()=>({first:()=>({json:{mediaType,media:{title:'Example',year:2020,tmdbId:11,tvdbId:22,titleSlug:'example',seasons:[{seasonNumber:0,monitored:true},{seasonNumber:1,monitored:true}]}}})})})));}
 const m=build('movie')[0].json;assert.equal(m.tmdbId,11);assert.equal(m.addOptions.searchForMovie,false);
 const t=build('tv')[0].json;assert.equal(t.tvdbId,22);assert.equal(t.monitored,false);assert.equal(t.monitorNewItems,'none');assert.equal(t.addOptions.searchForMissingEpisodes,false);assert.ok(t.seasons.every(s=>!s.monitored));
});
