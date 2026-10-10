const test=require('node:test'),assert=require('node:assert/strict');
const p=require('../n8n/request-simplification/policy.js');
const retention=require('../n8n/retention/policy.js');
const row=()=>({id:1,source:'discord',userId:'111',destinationId:'333',mediaType:'tv',mediaJson:JSON.stringify({title:'Example',tvdbId:123,seasons:Array.from({length:45},(_,i)=>({seasonNumber:i+1}))}),contextJson:'{}',state:'scope',choice:'',expiresAt:'2099-01-01'});
const actor=action=>({source:'discord',userId:'111',destinationId:'333',action});
function advance(r,action){const a=actor(action),state=p.transition(r,a,Date.now());return {...p.revise(r,a,state),choice:p.selectedChoice(r,a,state)};}
test('toggle several seasons, deselect, and review once before final confirmation',()=>{
 let r=advance(row(),'choose');r=advance(r,'season_3');assert.equal(r.state,'seasons');r=advance(r,'season_1');
 assert.match(p.card(r).text,/Selected: Seasons 1, 3/);assert.match(p.card(r).choices.find(c=>c.action==='season_3').label,/✅/);
 r=advance(r,'season_3');assert.doesNotMatch(p.card(r).choices.find(c=>c.action==='season_3').label,/✅/);
 r=advance(r,'season_2');r=advance(r,'review');assert.equal(r.state,'ready');assert.equal(r.choice,'seasons_1_2');
 assert.match(p.card(r).text,/Selected: Seasons 1, 2/);assert.equal(advance(r,'confirm').choice,'seasons_1_2');
});
test('paging and Back preserve selections without refreshing deadline',()=>{
 let r=advance(advance(row(),'choose'),'season_2');r=advance(r,'page_1');r=advance(r,'season_21');
 r=advance(r,'review');r=advance(r,'back');assert.equal(r.state,'seasons');assert.equal(r.expiresAt,'2099-01-01');
 assert.match(p.card(r).choices.find(c=>c.action==='season_21').label,/✅/);r=advance(r,'page_0');assert.match(p.card(r).choices.find(c=>c.action==='season_2').label,/✅/);
 assert.equal(p.card(r).choices.length<=25,true);
});
test('empty, unavailable, off-page, expired and foreign selections fail closed',()=>{
 const r=advance(row(),'choose');assert.throws(()=>advance(r,'review'));assert.throws(()=>advance(r,'season_0'));assert.throws(()=>advance(r,'season_99'));assert.throws(()=>advance(r,'season_21'));assert.throws(()=>advance(r,'page_99'));
 assert.throws(()=>p.transition(r,{...actor('season_1'),userId:'other'},Date.now()));assert.throws(()=>advance({...r,expiresAt:'2020-01-01'},'season_1'));
 assert.throws(()=>advance({...r,state:'ready',choice:'seasons_1_99'},'confirm'));
});
test('changing titles clears the previous season selections',()=>{
 let r=advance(advance(row(),'choose'),'season_2');r=advance(r,'back');r=advance(r,'wrong');
 r=advance(r,'match_0');r=advance(r,'choose');assert.throws(()=>advance(r,'review'));
});
test('combined subscription includes chosen seasons and future seasons, excludes older unchosen seasons and specials',()=>{
 const now=Date.parse('2026-10-09'),episodes=[0,1,2,3,4].map(s=>({id:s+1,seasonNumber:s,episodeNumber:1,airDateUtc:'2025-01-01'}));
 const s=retention.subscription(episodes,'seasons_1_3',now);assert.deepEqual(s.selectedSeasons,[1,3]);assert.deepEqual(s.episodeIds,['2','4']);
 assert.equal(retention.belongsToSubscription({id:9,seasonNumber:5,episodeNumber:1},s),true);
 for(const choice of ['seasons_','seasons_0_1','seasons_1_1','seasons_3_1','seasons_1_99'])assert.throws(()=>retention.subscription(episodes,choice,now));
});
