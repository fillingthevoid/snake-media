const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const file=__dirname+'/../n8n/retention/policy.js';
function policy(){const module={exports:{}};if(fs.existsSync(file))vm.runInNewContext(fs.readFileSync(file,'utf8'),{module,Date});return module.exports;}
const day=n=>new Date(Date.UTC(2026,0,1+n)).toISOString();
test('retention defaults and explicit permanent/custom overrides reject ambiguous instructions',()=>{
 const p=policy();assert.equal(typeof p.parseRetention,'function');
 assert.equal(p.parseRetention('add Alien from 1979','movie').days,7);
 assert.equal(p.parseRetention('get Severance','tv').days,30);
 assert.equal(p.parseRetention('add Alien, keep for 14 days','movie').days,14);
 assert.equal(p.parseRetention('add Severance, keep permanently','tv').days,null);
 for(const s of ['keep for 0 days','keep for -2 days','keep for 1.5 days','keep for 4000 days','keep for two weeks','keep permanently, delete after 7 days','keep for 7 days and keep for 8 days'])assert.throws(()=>p.parseRetention('add Alien, '+s,'movie'));
});
test('watched expiry shortens but never resets the independent import clock',()=>{
 const p=policy();assert.equal(typeof p.effectiveExpiry,'function');
 assert.equal(p.effectiveExpiry(day(0),7,day(6)),day(7));
 assert.equal(p.effectiveExpiry(day(0),30,day(4)),day(11));
 assert.equal(p.effectiveExpiry(day(0),30,day(28)),day(30));
 assert.equal(p.effectiveExpiry(day(3),30,null),day(33));
 assert.equal(p.effectiveExpiry(day(0),30,day(20),day(11)),day(11));
 assert.equal(p.effectiveExpiry(day(0),null,day(1)),null);
 assert.throws(()=>p.effectiveExpiry('bad',7,null));
});
const episodes=[
 {id:1,seasonNumber:0,episodeNumber:1,airDateUtc:day(-100)},
 {id:2,seasonNumber:1,episodeNumber:1,airDateUtc:day(-90)},
 {id:3,seasonNumber:2,episodeNumber:1,airDateUtc:day(-5)},
 {id:4,seasonNumber:2,episodeNumber:2,airDateUtc:day(5)},
 {id:5,seasonNumber:3,episodeNumber:1,airDateUtc:day(90)}];
test('subscriptions include selected airing and future seasons but not older unselected seasons',()=>{
 const p=policy();assert.equal(typeof p.subscription,'function');
 const s=p.subscription(episodes,'latest',Date.parse(day(0)));
 assert.deepEqual(Array.from(s.episodeIds),['3','4','5']);
 assert.deepEqual(Array.from(s.historicalSeasons),[1,2]);
 assert.equal(p.belongsToSubscription({...episodes[4],id:6,seasonNumber:4},s),true);
 assert.equal(p.belongsToSubscription(episodes[1],s),false);
 assert.equal(p.belongsToSubscription(episodes[0],s),false);
 assert.equal(p.subscription([episodes[4]],'latest',Date.parse(day(0))).episodeIds[0],'5');
});
test('permanent, unknown, preexisting and overlapping claims protect shared physical files',()=>{
 const p=policy();assert.equal(typeof p.fileDecision,'function');
 const claim={baselineCaptured:true,preexisting:false,days:7,importedAt:day(0),watchedAt:null,episodeIds:['2']};
 assert.equal(p.fileDecision([claim],['2'],Date.parse(day(8))).due,true);
 for(const patch of [{days:null},{baselineCaptured:false},{preexisting:true}])assert.equal(p.fileDecision([{...claim,...patch}],['2'],Date.parse(day(40))).due,false);
 assert.equal(p.fileDecision([claim,{...claim,days:30}],['2'],Date.parse(day(8))).due,false);
 assert.equal(p.fileDecision([claim],['2','3'],Date.parse(day(40))).due,false);
 assert.equal(p.fileDecision([] ,['2'],Date.parse(day(40))).due,false);
});
test('removed media is skipped while service failures remain errors',()=>{
 const p=policy();assert.equal(typeof p.mediaSnapshot,'function');
 assert.equal(p.mediaSnapshot({statusCode:404}),null);
 assert.equal(p.mediaSnapshot({statusCode:200,body:{id:12}}).id,12);
 for(const r of [{statusCode:401},{statusCode:500},{statusCode:200,body:{}}])assert.throws(()=>p.mediaSnapshot(r));
});
