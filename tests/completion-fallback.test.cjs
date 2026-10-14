const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const policy=require('../n8n/polish/presentation/policy.js');
test('malformed optional artwork cannot prevent a verified completion result',()=>{
 const c={request:{mediaType:'movie',mediaId:'9'},fileId:'10',jellyfinPath:'/data/movies/a.mkv',importedAt:'2026-10-13T10:00:00Z',quality:'1080p'};
 for(const media of [null,undefined,{error:'offline'},{images:'bad response'},{images:[null]}]){
  const result=policy.completion(c,[],{Id:'abc'},media);assert.match(result.jellyfinUrl,/details\?id=abc$/);
  assert.equal(result.expiryText,'Expiry check pending.');assert.equal(result.quality,'1080p');assert.equal(result.posterUrl,undefined);
 }
});
test('canonical enrichment preserves the queued notice when optional metadata is unavailable',()=>{
 const rows=JSON.parse(fs.readFileSync('config-templates/n8n-current-media-workflows.json','utf8'));
 const w=rows.find(x=>x.id==='snakeQueueCandidateV1'),node=w.nodes.find(n=>n.name==='Enrich Completion Notice');
 const c={request:{mediaType:'movie',mediaId:'9'},fileId:'10',jellyfinPath:'/data/movies/a.mkv',importedAt:'2026-10-13T10:00:00Z',quality:'1080p',jellyfinItems:[{Id:'abc',Path:'/data/movies/a.mkv'}]};
 const original={notificationKey:'r:movie:9',requestKey:'r',destinationId:'30',state:'pending',payloadJson:JSON.stringify({text:'Available in Jellyfin',userId:'10',messageId:'40'})};
 const input={'Candidate Input':c,'Build Completion Notice':original};
 const $=name=>({first:()=>({json:input[name]}),all:()=>[]});
 const run=new Function('$','$json',node.parameters.jsCode);
 for(const media of [{error:'offline'},{images:'bad response'}]){
  const out=run($,media)[0].json;assert.equal(out.notificationKey,'r:movie:9');assert.equal(out.state,'pending');
  const p=JSON.parse(out.payloadJson);assert.match(p.text,/Available in Jellyfin/);assert.match(p.text,/Expiry check pending/);assert.equal(p.userId,'10');assert.match(p.jellyfinUrl,/details\?id=abc$/);
 }
 for(const name of ['Read Completion Media','Read Completion Series'])assert.equal(w.nodes.find(n=>n.name===name).onError,'continueRegularOutput');
});
