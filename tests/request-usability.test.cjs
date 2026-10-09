const test=require('node:test'),assert=require('node:assert/strict');
const p=require('../n8n/request-simplification/policy.js');
const now=Date.now(),actor=action=>({source:'discord',userId:'111',destinationId:'333',action});
const row=()=>({id:1,source:'discord',userId:'111',destinationId:'333',mediaType:'tv',state:'scope',choice:'',claimId:'a',expiresAt:new Date(now+300000).toISOString(),mediaJson:JSON.stringify({title:'Example',tvdbId:1,seasons:[{seasonNumber:1}]}),contextJson:JSON.stringify({retentionPolicy:{days:30},titleMatches:{active:false,items:[{title:'Example',tvdbId:1,seasons:[{seasonNumber:1}]},{title:'Another Example',tvdbId:2,seasons:[{seasonNumber:2}]}]}})});
test('wrong title lists alternatives and selecting one still requires season and final confirmation',()=>{
 const r=row();assert.ok(p.card(r).choices.some(c=>c.action==='wrong'));
 const state=p.transition(r,actor('wrong'),now),next=p.revise(r,actor('wrong'),state);
 assert.ok(p.card(next).choices.some(c=>c.action==='match_1'));
 assert.throws(()=>p.transition(next,actor('confirm'),now));
 const selected=p.revise(next,actor('match_1'),p.transition(next,actor('match_1'),now));
 assert.equal(JSON.parse(selected.mediaJson).tvdbId,2);assert.equal(selected.state,'scope');assert.equal(selected.choice,'');
 assert.throws(()=>p.transition(selected,actor('confirm'),now));
});
test('alternative title choices enforce owner, deadline and offered indices',()=>{
 const r=row();assert.throws(()=>p.transition(r,{...actor('wrong'),userId:'222'},now));
 assert.throws(()=>p.transition(r,actor('wrong'),now+300001));
 const next=p.revise(r,actor('wrong'),p.transition(r,actor('wrong'),now));
 assert.throws(()=>p.transition(next,actor('match_9'),now));
 assert.throws(()=>p.transition(r,actor('match_1'),now));
});
test('Back from seasons or final selection cannot submit a download',()=>{
 assert.equal(p.transition({...row(),state:'seasons'},actor('back'),now),'scope');
 assert.equal(p.transition({...row(),state:'ready',choice:'season_1'},actor('back'),now),'seasons');
 const r=row(),next=p.revise(r,actor('wrong'),p.transition(r,actor('wrong'),now));
 assert.equal(JSON.parse(p.revise(next,actor('back'),p.transition(next,actor('back'),now)).contextJson).titleMatches.active,false);
});
test('Cancel from alternative matches closes the request without selecting a title',()=>{
 const r=row(),next=p.revise(r,actor('wrong'),p.transition(r,actor('wrong'),now));
 const closed=p.revise(next,actor('cancel'),p.transition(next,actor('cancel'),now));
 assert.equal(closed.state,'cancelled');assert.match(p.card(closed).text,/No media was added/);
});
test('empty My requests offers a request prompt and recommendations',()=>{
 const m=require('../n8n/my-requests/policy.js');
 const c=m.create({...actor(''),messageId:'444',requestedAt:new Date(now).toISOString()},[],now);
 assert.deepEqual(c.menuChoices.map(x=>x.action),['request','recommend']);
});
test('category filters use owned fresh tracking and never label stale records ready',()=>{
 const m=require('../n8n/my-requests/policy.js'),a={...actor(''),messageId:'444',requestedAt:new Date(now).toISOString()};
 const requests=[{...a,state:'registered',requestKey:'r1',mediaType:'movie',mediaId:'9',title:'Ready movie'},{...a,state:'registered',requestKey:'r2',mediaType:'tv',mediaId:'10',title:'Downloading show',episodeIdsJson:'["3"]'}];
 const file={key:'file:movie:9:1',kind:'file',payloadJson:JSON.stringify({mediaType:'movie',mediaId:'9',fileId:1,state:'tracked',path:'/movies/a.mkv',importedAt:new Date(now-3600000).toISOString(),checkedAt:new Date(now).toISOString(),expiresAt:new Date(now+86400000).toISOString()})};
 const evidence={records:[file],notices:[{requestKey:'r1',state:'delivered',notificationKey:'r1:movie:9',fileKey:'movie:9',deliveredAt:new Date(now-1000).toISOString()}],events:[{mediaType:'tv',mediaId:'10',state:'downloading',receivedAt:new Date(now).toISOString(),episodeIdsJson:'["3"]'}]};
 const r={...m.create(a,requests,now,evidence),id:5};
 assert.equal(JSON.parse(r.contextJson).myRequests.titles[0].category,'expiring');
 const filtered=m.advance(r,{...a,action:'mr_filter_downloading'},now,'new');
 const card=m.card(filtered.record,now);assert.equal(card.choices.filter(c=>c.action.startsWith('mr_title_')).length,1);assert.match(card.choices.find(c=>c.action.startsWith('mr_title_')).label,/Downloading show/);
 assert.throws(()=>m.advance(filtered.record,{...a,action:'mr_title_0'},now,'bad'));
 const stale=m.create(a,requests,now+3600000,evidence);assert.ok(JSON.parse(stale.contextJson).myRequests.titles.every(t=>t.category==='other'));
});
test('retention confirmation previews dates from fresh scoped records and Back restores durations',t=>{
 const now=Date.parse('2026-10-09T12:00:00Z');t.mock.method(Date,'now',()=>now);
 const r=require('../n8n/retention-controls/policy.js');
 const change={operation:'extend',days:7,title:'Example',source:'discord',userId:'111',mediaType:'movie',mediaId:'9',requestKeys:['r1']};
 const file={key:'file:movie:9:1',kind:'file',payloadJson:JSON.stringify({state:'tracked',fileId:1,mediaType:'movie',mediaId:'9',path:'/movies/a.mkv',importedAt:'2026-10-01T12:00:00Z',checkedAt:new Date(now).toISOString(),expiresAt:'2026-11-01T12:00:00Z'})};
 const a={...actor(''),text:'extend',messageId:'444'};
 const result=r.prepareChange(a,[{...a,state:'registered',requestKey:'r1',mediaType:'movie',mediaId:'9',title:'Example'}],[file],now);
 let row={id:5,...actor(''),state:'preview',expiresAt:new Date(now+300000).toISOString(),contextJson:JSON.stringify({retentionGuide:{...result.guide,selected:0}})};
 row={...row,...r.guideAction(row,actor('retdays_7'),now)};
 const card=r.changeCard(row);assert.match(card.text,/Nov 8, 2026/);assert.ok(card.choices.some(c=>c.action==='retback'));
 const back=r.guideAction(row,actor('retback'),now);assert.equal(JSON.parse(back.contextJson).retentionGuide.days,undefined);
 assert.match(r.changeCard({...row,...back}).choices[0].label,/Extend by 7 days/);
});
test('recommendation Back restores type or genre without generating or downloading',()=>{
 const r=require('../n8n/recommendations/policy.js'),a={...actor(''),messageId:'444',requestedAt:new Date(now).toISOString()};
 let row={...r.record(a,now),id:5};row=r.transition(row,{...a,action:'rec_tv'},now,'a').record;
 assert.ok(r.card(row,now).choices.some(c=>c.action==='rec_back'));
 const back=r.transition(row,{...a,action:'rec_back'},now,'b');
 assert.equal(back.generate,false);assert.equal(back.preview,null);assert.equal(JSON.parse(back.record.contextJson).recommendation.stage,'type');
});
test('expiring imported files without a Jellyfin confirmation stay out of Ready to watch',()=>{
 const m=require('../n8n/my-requests/policy.js'),a={...actor(''),messageId:'444',requestedAt:new Date(now).toISOString()};
 const request={...a,state:'registered',requestKey:'r1',mediaType:'movie',mediaId:'9',title:'Not ready'};
 const record={key:'file:movie:9:1',payloadJson:JSON.stringify({state:'tracked',mediaType:'movie',mediaId:'9',fileId:1,path:'/movies/a.mkv',importedAt:new Date(now-1000).toISOString(),checkedAt:new Date(now).toISOString(),expiresAt:new Date(now+86400000).toISOString()})};
 const r={...m.create(a,[request],now,{records:[record]}),id:5};
 const next=m.advance(r,{...a,action:'mr_filter_ready'},now,'a');
 assert.equal(m.card(next.record,now).choices.filter(c=>c.action.startsWith('mr_title_')).length,0);
});
