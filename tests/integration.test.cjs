const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function run(file,input,refs={}) { return JSON.parse(JSON.stringify(vm.runInNewContext('(function(){'+fs.readFileSync(__dirname+'/../n8n/tracking/code/'+file,'utf8')+'})()',{$input:{first:()=>({json:input}),all:()=>input.map?.(json=>({json}))||[{json:input}]},$:name=>({first:()=>({json:refs[name]})})}))); }
const context={source:'discord',userId:'100000000000000001',destinationId:'100000000000000004',messageId:'1554232153489805399',requestedAt:'2026-09-29T00:00:00.000Z',text:'add Matrix'};
test('result normalization preserves stable metadata and public poster',()=>{
 const r=run('media-result.js',{id:12,tmdbId:603,title:'Matrix',images:[{coverType:'poster',remoteUrl:'https://image.tmdb.org/t/p/original/abc.jpg'}]}, {'Integration Input':{context,mediaType:'movie',result:{id:12,tmdbId:603,title:'Matrix'}}})[0].json;
 assert.equal(r.mediaId,'12');assert.equal(r.externalId,'603');assert.equal(r.posterUrl,'https://image.tmdb.org/t/p/original/abc.jpg');assert.equal(r.context.messageId,context.messageId);
});
test('unsafe artwork is omitted, malformed results cannot report success',()=>{
 const refs={'Integration Input':{context,mediaType:'movie',result:{}}};
 assert.equal(run('media-result.js',{},refs)[0].json.status,'not_found');
 const r=run('media-result.js',{id:1,tmdbId:2,title:'X',images:[{coverType:'poster',remoteUrl:'http://192.168.1.10/poster'}]},refs)[0].json;
 assert.equal(r.posterUrl,undefined);
});
test('tracking snapshot protects existing movie files and excludes unknown future episodes',()=>{
 const movie={context,mediaType:'movie',mediaId:'12',externalId:'603',title:'Matrix',status:'already_added',raw:{movieFile:{id:88}}};
 const m=run('tracking-input.js',[],{'Normalize Media Metadata':movie})[0].json;
 assert.deepEqual(m.preexistingFileIds,['88']);assert.equal(m.baselineCaptured,true);assert.equal(m.retentionDays,null);
 const tv={...movie,mediaType:'tv',status:'added',raw:{}};
 const t=run('tracking-input.js',[{id:1,episodeFileId:0},{id:2,episodeFileId:9}],{'Normalize Media Metadata':tv})[0].json;
 assert.deepEqual(t.episodeIds,['1','2']);assert.deepEqual(t.preexistingFileIds,[]);
 assert.throws(()=>run('tracking-input.js',[],{'Normalize Media Metadata':tv}),/episode scope/);
});
