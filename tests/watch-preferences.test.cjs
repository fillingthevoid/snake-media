const test=require('node:test'),assert=require('node:assert/strict');
const p=require('../n8n/watch-preferences/policy.js');
const a={source:'discord',userId:'111'};
const reply={version:1,status:'notice',text:'Available',jellyfinUrl:'https://remote.example/web/index.html#!/details?id=abc',localJellyfinUrl:'http://192.168.1.10:8096/web/index.html#!/details?id=abc'};
const row=(id,choice,extra={})=>({id,source:'discord',userId:'111',state:'settings',contextJson:JSON.stringify({watchPreference:choice}),...extra});
test('watch preference uses newest valid record for this platform and immutable user',()=>{
 const rows=[row(1,'tailscale'),row(2,'local'),row(3,'tailscale',{userId:'222'}),row(4,'tailscale',{source:'telegram'})];
 const out=p.apply(reply,rows,a);assert.equal(out.jellyfinUrl,reply.localJellyfinUrl);assert.equal(out.localJellyfinUrl,undefined);
 assert.deepEqual(p.apply(reply,[],a),reply);assert.deepEqual(p.apply(reply,[row(5,'both')],a),reply);
 const remote=p.apply(reply,[row(5,'tailscale')],a);assert.equal(remote.jellyfinUrl,reply.jellyfinUrl);assert.equal(remote.localJellyfinUrl,undefined);
 assert.deepEqual(reply.localJellyfinUrl,'http://192.168.1.10:8096/web/index.html#!/details?id=abc');
});
test('malformed settings and unavailable preferred address preserve usable links',()=>{
 assert.deepEqual(p.apply(reply,[row(5,'bogus')],a),reply);
 assert.deepEqual(p.apply(reply,[{...row(5,'local'),contextJson:'bad'}],a),reply);
 const remoteOnly={...reply};delete remoteOnly.localJellyfinUrl;
 assert.deepEqual(p.apply(remoteOnly,[row(5,'local')],a),remoteOnly);
});
test('settings survive normal pending-choice compaction',()=>{
 const m=require('../n8n/maintenance/policy.js');
 assert.equal(m.retireChoice({...row(1,'local'),expiresAt:'2100-01-01T00:00:00Z',updatedAt:'2025-01-01T00:00:00Z'},Date.now()),null);
});
