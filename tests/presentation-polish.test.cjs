const {test}=require('node:test'),a=require('node:assert/strict');
const p=require('../n8n/polish/presentation/policy.js');
test('progress gives bounded actual percentage, ETA and release quality',()=>{
 a.match(p.progress({status:'downloading',size:100,sizeleft:25,timeleft:'00:04:00',quality:{quality:{name:'WEB-1080p'}}}),/75%.*00:04:00.*WEB-1080p/);
 a.doesNotMatch(p.progress({size:0,sizeleft:25}),/NaN|Infinity|%/);
});
test('completion verifies exact file identity before exposing expiry and builds local Jellyfin link',()=>{
 const c={request:{mediaType:'movie',mediaId:'8'},fileId:'4',importedAt:'2026-10-01T00:00:00Z',jellyfinPath:'/data/movies/a.mkv',quality:'Bluray-1080p'};
 const record={key:'file:movie:8:4',payloadJson:JSON.stringify({state:'tracked',path:'/movies/a.mkv',importedAt:c.importedAt,expiresAt:'2026-10-08T00:00:00Z',checkedAt:c.importedAt})};
 const m=p.completion(c,[record],{Id:'abc'},{images:[{coverType:'poster',remoteUrl:'https://image.tmdb.org/t/p/w500/a.jpg'}]});
 a.equal(m.jellyfinUrl,'http://192.168.1.10:8096/web/index.html#!/details?id=abc');a.match(m.expiryText,/Oct 7/);a.equal(m.quality,'Bluray-1080p');
 record.payloadJson=record.payloadJson.replace('/movies/a.mkv','/movies/b.mkv');a.match(p.completion(c,[record],{Id:'abc'},{}).expiryText,/pending/);
});
test('waiting release feedback states that no acceptable release is currently downloading',()=>{
 a.match(p.feedback({status:'added',searchStarted:true,title:'Example'}),/accepted.*Search started/s);
 a.match(p.feedback({status:'already_added',title:'Example'}),/status/);
});

test('progress notifications are once per request and do not notify after verified completion',()=>{
 const r={requestKey:'discord:2:3',source:'discord',destinationId:'4',userId:'2',messageId:'3',requestedAt:'2026-10-01T00:00:00Z'};
 const now=Date.parse('2026-10-01T00:20:00Z');
 const result=p.progressNotice(r,{text:'Example\n⬇️ Downloading\n⬇️ 75% · ETA 00:04:00 · WEB-1080p',progressState:'downloading'},[],now);
 a.equal(result.notificationKey,'discord:2:3:progress:downloading');a.match(JSON.parse(result.payloadJson).text,/Download started.*75%/s);
 a.equal(p.progressNotice(r,{text:'Downloading',progressState:'downloading'},[result],now),null);
 a.equal(p.progressNotice(r,{text:'waiting for a release',progressState:'waiting'},[],now).notificationKey,'discord:2:3:progress:no-release');
 a.equal(p.progressNotice(r,{text:'waiting for a release',progressState:'waiting'},[{requestKey:r.requestKey,notificationKey:r.requestKey+':tv-ready'}],now),null);
 a.equal(p.progressNotice({...r,userId:'1'},{text:'Downloading',progressState:'downloading'},[],now),null);
});
test('delivered progress cannot suppress the once-per-request TV completion',()=>{
 const c={request:{requestKey:'d:2:3'},mediaType:'tv',fileKey:'tv:8:episode:1'};
 a.equal(p.completionExists(c,[{requestKey:'d:2:3',notificationKey:'d:2:3:progress:downloading',state:'delivered'}]),false);
 a.equal(p.completionExists(c,[{requestKey:'d:2:3',notificationKey:'d:2:3:tv-ready',state:'pending'}]),true);
 a.equal(p.completionExists(c,[{requestKey:'d:2:3',notificationKey:'d:2:3:tv:8:episode:2',state:'delivered'}]),true);
});
test('negative waiting feedback and unreleased snapshots never report a download start',()=>{
 const r={requestKey:'discord:2:3',source:'discord',destinationId:'4',userId:'2',messageId:'3',requestedAt:'2026-10-01T00:00:00Z'},now=Date.parse('2026-10-01T00:20:00Z');
 const text='Example\nWaiting for a release\nNo acceptable release is downloading yet.';
 a.equal(p.progressNotice(r,{text},[],now),null);
 a.equal(p.progressNotice(r,{text,progressState:'waiting'},[],now).fileKey,'progress:no-release');
 a.equal(p.progressNotice(r,{text:'Awaiting release',progressState:null},[],now),null);
});
test('season-pack progress is scoped to requested episode metadata',()=>{
 const requests=[{requestKey:'d:2:3',mediaType:'tv',mediaId:'8',episodeIdsJson:'["11"]'}];
 const episodes=[{id:11,seasonNumber:1,episodeNumber:1},{id:21,seasonNumber:2,episodeNumber:1}];
 const other={seriesId:8,seasonNumber:2,status:'downloading',size:100,sizeleft:50};
 a.deepEqual(p.scopedQueue(requests,episodes,[other]),[]);
 a.deepEqual(p.scopedQueue(requests,episodes,[{...other,seasonNumber:1}]),[{...other,seasonNumber:1}]);
 a.deepEqual(p.scopedQueue(requests,episodes,[{...other,seasonNumber:undefined},{...other,seasonNumber:'1'},{...other,episodeId:21}]),[]);
 a.equal(p.scopedQueue(requests,episodes,[{...other,episodeId:11}]).length,1);
 const actor={...requests[0],source:'discord',destinationId:'4',userId:'2',messageId:'3',requestedAt:'2026-10-01T00:00:00Z'};
 const status=require('../n8n/status/policy.js');
 const snapshot=queue=>({text:status.describe({requests:[actor],records:[],media:{id:8},episodes,queue,library:[],now:Date.parse('2026-10-01T00:20:00Z')}),progressState:p.scopedQueue([actor],episodes,queue).some(q=>q.status==='downloading')?'downloading':'waiting'});
 a.equal(p.progressNotice(actor,snapshot([other]),[],Date.parse('2026-10-01T00:20:00Z')).fileKey,'progress:no-release');
 a.equal(p.progressNotice(actor,snapshot([{...other,seasonNumber:1}]),[],Date.parse('2026-10-01T00:20:00Z')).fileKey,'progress:downloading');
});
test('completion/status links expose local and Tailnet bases without duplicates',()=>{
 a.deepEqual(p.jellyfinLinks({Id:'abc'},'http://100.100.100.100:8096','http://192.168.1.10:8096'),{jellyfinUrl:'http://100.100.100.100:8096/web/index.html#!/details?id=abc',localJellyfinUrl:'http://192.168.1.10:8096/web/index.html#!/details?id=abc'});
 a.equal(p.jellyfinLinks({Id:'abc'},'http://192.168.1.10:8096','http://192.168.1.10:8096').localJellyfinUrl,undefined);
 a.equal(p.jellyfinLinks({Id:'abc'},'http://100.100.100.100:8096','').localJellyfinUrl,undefined);
});
