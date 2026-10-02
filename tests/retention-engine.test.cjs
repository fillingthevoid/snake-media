const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root=__dirname+'/../n8n/retention/';
function engine(){const module={exports:{}};for(const f of ['policy.js','engine.js'])if(fs.existsSync(root+f))vm.runInNewContext(fs.readFileSync(root+f,'utf8'),{module,Date,...module.exports});return module.exports;}
const date=n=>new Date(Date.UTC(2026,0,1+n)).toISOString();
function fixture(){return {now:Date.parse(date(40)),requests:[{requestKey:'discord:1:2',mediaType:'tv',mediaId:'2',title:'Show',requestedAt:date(0),baselineCaptured:true,retentionDays:30,episodeIdsJson:'["10"]',preexistingFileIdsJson:'[]'}],records:[{key:'request:discord:1:2',kind:'subscription',payloadJson:JSON.stringify({requestKey:'discord:1:2',mediaType:'tv',mediaId:'2',historicalSeasons:[1],selectedSeasons:[1],episodeIds:['10']})}],media:{id:2},episodes:[{id:10,seasonNumber:1,episodeNumber:1,episodeFileId:100,airDateUtc:date(0),episodeFile:{id:100,path:'/tv/Show/a.mkv',dateAdded:date(1)}}],watched:[],sessions:[]};}
test('engine creates a per-file due decision only for new policy requests',()=>{
 const p=engine();assert.equal(typeof p.planMedia,'function');const f=fixture(),out=p.planMedia(f);
 assert.equal(out.deletions.length,1);assert.equal(out.deletions[0].fileId,100);
 f.requests[0].retentionDays=null;assert.equal(p.planMedia(f).deletions.length,0);
 f.requests[0].retentionDays=30;f.records=[];assert.equal(p.planMedia(f).deletions.length,0);
});
test('any users watched state shortens one episode while shared claims and sessions protect it',()=>{
 const p=engine();assert.equal(typeof p.planMedia,'function');const f=fixture();f.now=Date.parse(date(12));
 f.watched=[{Id:'j',Path:'/data/tv/Show/a.mkv',ParentIndexNumber:1,IndexNumber:1,UserData:{Played:true,LastPlayedDate:date(4)}}];
 assert.equal(p.planMedia(f).deletions.length,1);
 f.sessions=[{NowPlayingItem:{Id:'j',Path:'/data/tv/Show/a.mkv'}}];assert.equal(p.planMedia(f).deletions.length,0);
 f.sessions=[];f.requests.push({...f.requests[0],requestKey:'telegram:3:4',retentionDays:null});assert.equal(p.planMedia(f).deletions.length,0);
});
test('future episode is persisted before monitoring and expired episode stays unmonitored',()=>{
 const p=engine();assert.equal(typeof p.planMedia,'function');const f=fixture();
 f.episodes.push({id:11,seasonNumber:2,episodeNumber:1,airDateUtc:date(50),episodeFileId:0});
 f.records.push({key:'file:tv:2:100',kind:'file',payloadJson:JSON.stringify({state:'deleted',episodeIds:['10'],deletedAt:date(39)})});
 const out=p.planMedia(f);assert.deepEqual(Array.from(out.monitorIds),[11]);
 assert.ok(out.records.some(r=>r.kind==='subscription'&&JSON.parse(r.payloadJson).episodeIds.includes('11')));
 assert.equal(out.deletions.length,0);
});
test('multi-episode file waits for all episodes and duplicate claims fail closed',()=>{
 const p=engine();assert.equal(typeof p.planMedia,'function');const f=fixture();
 f.episodes.push({...f.episodes[0],id:11,episodeNumber:2});
 assert.equal(p.planMedia(f).deletions.length,0);
 f.requests.push({...f.requests[0]});assert.throws(()=>p.planMedia(f));
});
test('changed identity under the same file ID stays protected across scans',()=>{
 const p=engine(),f=fixture();
 f.records.push({key:'file:tv:2:100',kind:'file',payloadJson:JSON.stringify({state:'tracked',path:'/tv/Show/old.mkv',importedAt:date(1),deadlines:{}})});
 const out=p.planMedia(f);assert.equal(out.deletions.length,0);
 f.records=out.records;assert.equal(p.planMedia(f).deletions.length,0);
});
test('unknown active playback and malformed request timestamps cannot authorize deletion',()=>{
 const p=engine(),f=fixture();f.sessions=[{NowPlayingItem:{Id:'unknown'}}];
 assert.equal(p.planMedia(f).deletions.length,0);
 f.requests[0].requestedAt='invalid';assert.throws(()=>p.planMedia(f));
});

test('explicit extension survives watched shortening and rescans without moving each time',()=>{
 const p=engine(),f=fixture();
 const edit={version:1,operation:'extend',requestKeys:['discord:1:2'],mediaType:'tv',mediaId:'2',files:[{fileId:100,path:'/tv/Show/a.mkv',importedAt:date(1),minimumExpiry:date(60)}]};
 const record={key:'change:12',kind:'amendment',payloadJson:JSON.stringify(edit)};f.records.push(record);
 f.watched=[{Id:'j',Path:'/data/tv/Show/a.mkv',ParentIndexNumber:1,IndexNumber:1,UserData:{Played:true,LastPlayedDate:date(3)}}];
 let out=p.planMedia(f);assert.equal(out.deletions.length,0);assert.equal(out.decisions[0].expiresAt,date(60));
 f.records=[...out.records,record];f.watched[0].UserData.LastPlayedDate=date(41);f.now=Date.parse(date(42));
 out=p.planMedia(f);assert.equal(out.decisions[0].expiresAt,date(60));
 f.episodes[0].episodeFile={id:101,path:'/tv/Show/new.mkv',dateAdded:date(2)};f.episodes[0].episodeFileId=101;
 assert.notEqual(p.planMedia(f).decisions[0].expiresAt,date(60));
});
test('permanent amendment protects future subscribed files and leaves other requests intact',()=>{
 const p=engine(),f=fixture();f.records.push({key:'change:13',kind:'amendment',payloadJson:JSON.stringify({version:1,operation:'permanent',requestKeys:['discord:1:2'],mediaType:'tv',mediaId:'2',files:[]})});
 assert.equal(p.planMedia(f).decisions[0].expiresAt,null);
 f.records[1].payloadJson=JSON.stringify({version:1,operation:'permanent',requestKeys:['other'],mediaType:'tv',mediaId:'2',files:[]});
 assert.equal(p.planMedia(f).deletions.length,1);
});
