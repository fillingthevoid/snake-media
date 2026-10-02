const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
function run(file,rows,refs={}){return JSON.parse(JSON.stringify(vm.runInNewContext('(function(){'+fs.readFileSync(__dirname+'/../n8n/tracking/code/'+file,'utf8')+'})()',{$input:{all:()=>rows.map(json=>({json})),first:()=>({json:rows[0]})},$:n=>({first:()=>({json:refs[n]})}),Date})));}
const request={source:'discord',userId:'111',destinationId:'333',messageId:'444',requestKey:'discord:333:444',title:'Show',mediaType:'tv',mediaId:'3',externalId:'4',episodeIdsJson:'["10","11"]',preexistingFileIdsJson:'["99"]',requestedAt:'2026-09-29T00:00:00.000Z',baselineCaptured:true,retentionDays:null};
const episode={id:10,tvdbId:15,seasonNumber:1,episodeNumber:1,hasFile:true,episodeFileId:100,episodeFile:{id:100,path:'/tv/Show/S01/a.mkv',dateAdded:'2026-09-29T01:00:00Z'}};
const second={...episode,id:11,episodeNumber:2,episodeFileId:101,episodeFile:{...episode.episodeFile,id:101,path:'/tv/Show/S01/b.mkv'}};
const missing={...episode,hasFile:false,episodeFileId:0,episodeFile:undefined};

test('wait for earliest viewing-order episode even when later episodes import first',()=>{
 assert.equal(run('notification-candidates.js',[second,missing],{'Inspect Request':request}).length,0);
 const rows=run('notification-candidates.js',[second,episode],{'Inspect Request':request});
 assert.equal(rows.length,1);assert.equal(rows[0].json.fileId,'100');
});
test('choose across requested seasons and skip files present before request',()=>{
 const old={...episode,episodeFileId:99,episodeFile:{...episode.episodeFile,id:99}};
 const later={...second,seasonNumber:2,episodeNumber:1};
 const rows=run('notification-candidates.js',[later,old],{'Inspect Request':request});
 assert.equal(rows.length,1);assert.match(rows[0].json.label,/S02E01/);
 assert.equal(run('notification-candidates.js',[second],{'Inspect Request':request}).length,0);
});
test('one TV notice per request with accurate remaining-episode wording on both platforms',()=>{
 for(const source of ['discord','telegram']) {
  const r={...request,source,jellyfinLibrary:[{Path:'/data/tv/Show/S01/a.mkv',Id:'a'}]};
  const c=run('notification-candidates.js',[episode,{...missing,id:11,episodeNumber:2}],{'Inspect Request':r})[0].json;
  const out=run('confirm-jellyfin.js',[{Items:r.jellyfinLibrary}],{'Candidate Input':c})[0].json;
  assert.equal(out.notificationKey,request.requestKey+':tv-ready');
  assert.match(JSON.parse(out.payloadJson).text,/remaining episodes you requested will be available soon/i);
  const all={...r,jellyfinLibrary:[...r.jellyfinLibrary,{Path:'/data/tv/Show/S01/b.mkv',Id:'b'}]};
  const ready=run('notification-candidates.js',[second,episode],{'Inspect Request':all})[0].json;
  const done=run('confirm-jellyfin.js',[{Items:all.jellyfinLibrary}],{'Candidate Input':ready})[0].json;
  assert.match(JSON.parse(done.payloadJson).text,/all requested episodes are available/i);
 }
});
test('only imported requested episodes become candidates; old and unrelated files excluded',()=>{
 const rows=run('notification-candidates.js',[episode,{...episode,id:12},{...episode,id:11,episodeFile:{...episode.episodeFile,id:99}}],{'Inspect Request':request});
 assert.equal(rows.length,1);assert.equal(rows[0].json.fileKey,'tv:3:episode:10');assert.equal(rows[0].json.jellyfinPath,'/data/tv/Show/S01/a.mkv');
 assert.equal(run('notification-candidates.js',[{...episode,episodeFile:{...episode.episodeFile,dateAdded:'2026-09-28T01:00:00Z'}}],{'Inspect Request':request}).length,0);
});
test('availability requires the exact file path in Jellyfin and stable notification identity',()=>{
 const candidate={...run('notification-candidates.js',[episode,second],{'Inspect Request':request})[0].json};
 assert.equal(run('confirm-jellyfin.js',[{Items:[{Path:'/data/tv/other.mkv'}]}],{'Candidate Input':candidate}).length,0);
 const out=run('confirm-jellyfin.js',[{Items:[{Path:'/data/tv/Show/S01/a.mkv',Id:'j1'}]}],{'Candidate Input':candidate})[0].json;
 assert.equal(out.notificationKey,'discord:333:444:tv-ready');assert.equal(out.state,'pending');assert.match(JSON.parse(out.payloadJson).text,/S01E01/);assert.match(JSON.parse(out.payloadJson).text,/available in Jellyfin/);
});
test('synthetic records and unproven baselines never cause notifications',()=>{
 for(const patch of [{userId:'1'},{baselineCaptured:false},{episodeIdsJson:'[]'}]) assert.equal(run('notification-candidates.js',[episode],{'Inspect Request':{...request,...patch}}).length,0);
});

test('Telegram acknowledgement reads actual API envelope and rejects unconfirmed sends',()=>{
 const p=__dirname+'/../n8n/tracking/code/telegram-delivery-result.js';
 assert.equal(fs.existsSync(p),true,'delivery result validator exists');
 assert.equal(run('telegram-delivery-result.js',[{ok:true,result:{message_id:47}}])[0].json.deliveredMessageId,'47');
 for(const r of [{ok:false},{ok:true,result:{}},{ok:true,result:{message_id:'undefined'}},{}]) assert.throws(()=>run('telegram-delivery-result.js',[r]));
});

test('TV deduplication treats legacy delivered notices as completed and replaces legacy pending notices',()=>{
 const c={request,mediaType:'tv',fileKey:'tv:3:episode:10'};
 const old={requestKey:request.requestKey,notificationKey:request.requestKey+':tv:3:episode:11',state:'pending'};
 assert.equal(run('notice-dedup.js',[old],{'Candidate Input':c}).length,1);
 assert.equal(run('notice-dedup.js',[{...old,state:'delivered'}],{'Candidate Input':c}).length,0);
 assert.equal(run('notice-dedup.js',[{...old,notificationKey:request.requestKey+':tv-ready'}],{'Candidate Input':c}).length,0);
 const movie={...c,mediaType:'movie',fileKey:'movie:3'};
 assert.equal(run('notice-dedup.js',[old],{'Candidate Input':movie}).length,1);
 assert.equal(run('notice-dedup.js',[{...old,notificationKey:request.requestKey+':movie:3'}],{'Candidate Input':movie}).length,0);
});

test('both delivery readers omit legacy episode notices but retain movies and request notices',()=>{
 const records=['tv:3:episode:10','tv-ready','movie:3'].map(s=>({notificationKey:request.requestKey+':'+s,destinationId:'333',payloadJson:JSON.stringify({text:s})}));
 const discord=run('discord-queue-batch.js',records)[0].json.notifications;
 const telegram=run('telegram-queue-batch.js',records);
 assert.deepEqual(discord.map(x=>x.payload.text),['tv-ready','movie:3']);
 assert.deepEqual(telegram.map(x=>JSON.parse(x.json.payloadJson).text),['tv-ready','movie:3']);
});

test('single episode and movie keep concise completion messages',()=>{
 for(const c of [
  {request,mediaType:'tv',downloadCount:1,fileKey:'tv:3:episode:10',label:'Show — S01E01',jellyfinPath:'/file'},
  {request,mediaType:'movie',fileKey:'movie:3',label:'Movie',jellyfinPath:'/file'}]) {
  const row=run('confirm-jellyfin.js',[{Items:[{Path:'/file',Id:'j'}]}],{'Candidate Input':c})[0].json;
  assert.doesNotMatch(JSON.parse(row.payloadJson).text,/remaining|All requested/);
  if(c.mediaType==='movie')assert.equal(row.notificationKey,request.requestKey+':movie:3');
 }
});
