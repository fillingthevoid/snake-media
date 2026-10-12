const {test}=require('node:test'),a=require('node:assert/strict');
const p=require('../n8n/request-simplification/policy.js');
const row=()=>({id:1,source:'discord',userId:'111',destinationId:'333',mediaType:'tv',state:'scope',choice:'',expiresAt:'2099-01-01',mediaJson:JSON.stringify({title:'Example',year:2020,seasons:Array.from({length:22},(_,i)=>({seasonNumber:i+1})),images:[{coverType:'poster',remoteUrl:'https://image.tmdb.org/t/p/w500/abc.jpg'}]}),contextJson:JSON.stringify({retentionPolicy:{days:30}})});
const actor=action=>({source:'discord',userId:'111',destinationId:'333',action});
test('initial poster contains direct season toggles and still requires review plus final confirmation',()=>{
 let r=row(),card=p.card(r);a.ok(card.posterUrl);a.ok(card.choices.some(c=>c.action==='season_1'));a.ok(card.choices.some(c=>c.action==='latest'));a.ok(card.choices.some(c=>c.action==='all'));a.ok(!card.choices.some(c=>c.action==='choose'));a.ok(card.choices.length<=25);
 a.throws(()=>p.transition(r,actor('confirm'),Date.now()));
 const state=p.transition(r,actor('season_1'),Date.now());r=p.revise(r,actor('season_1'),state);a.deepEqual(JSON.parse(r.contextJson).selectedSeasons,[1]);
 a.equal(p.transition(r,actor('latest'),Date.now()),'ready');
 const page=p.transition(r,actor('page_1'),Date.now());r=p.revise(r,actor('page_1'),page);a.ok(p.card(r).choices.some(c=>c.action==='season_17'));
 a.throws(()=>p.transition(r,actor('season_1'),Date.now()));
 const ready=p.transition(r,actor('review'),Date.now());const choice=p.selectedChoice(r,actor('review'),ready);r={...r,state:ready,choice};a.equal(choice,'seasons_1');a.equal(p.transition(r,actor('confirm'),Date.now()),'processing');
 a.throws(()=>p.transition(row(),{...actor('season_1'),userId:'222'},Date.now()));
});
test('repeat result wording follows confirmed readiness, queue state and search acknowledgement',()=>{
 const {accepted}=require('../n8n/request-entry/policy.js');
 const base={version:1,status:'notice',text:'Confirmed search started.',title:'Example',mediaType:'movie',mediaId:'10',requestKey:'r',searchStarted:true,repeatRequest:true};
 let r=accepted(base,{availability:{available:1,total:1},jellyfinUrl:'http://media/web/index.html#!/details?id=abc'});a.match(r.text,/Ready to watch/);a.equal(r.jellyfinUrl.includes('abc'),true);
 r=accepted(base,{availability:{available:0,total:1,downloading:1}});a.match(r.text,/Already downloading/);a.doesNotMatch(r.text,/Ready to watch/);
 r=accepted(base,{availability:{available:0,total:1,downloading:0,queued:0,imported:0}});a.match(r.text,/Searching again/);
 r=accepted({...base,searchStarted:false},{error:'Unavailable'});a.doesNotMatch(r.text,/Ready to watch|Searching again/);
 r=accepted({...base,mediaType:'tv'},{availability:{available:1,total:3,downloading:1}});a.match(r.text,/Some requested episodes/);a.doesNotMatch(r.text,/^.*Ready to watch/);
 a.equal(accepted({version:1,status:'notice',busy:true,text:'Busy'},{}).busy,true);
});

test('native post-commit inspection is read-only and exact request identity reaches the status reader',()=>{
 const rows=JSON.parse(require('node:fs').readFileSync(require('node:path').join(__dirname,'../config-templates/n8n-current-media-workflows.json'),'utf8'));
 const commit=rows.find(w=>w.id==='snakeCommitMediaV1'),body=rows.find(w=>w.id==='snakeCommitMediaBodyV2');
 a.equal(commit.connections['Coordinate Commit'].main[0][0].node,'Inspect Commit Result?');
 const read=commit.nodes.find(n=>n.name==='Read Accepted Request Status');a.equal(read.parameters.workflowId.value,'snakeStatusV1');a.equal(read.onError,'continueRegularOutput');
 a.ok(!commit.nodes.some(n=>n.type.endsWith('.httpRequest')));
 const values={'Movie Snapshot':{source:'discord',userId:'111',title:'Example',mediaType:'movie',mediaId:'10',missing:true},'Register Movie Before Search':{requestKey:'new-request'},'Existing Movie':{id:10}};
 const $=name=>({first:()=>({json:values[name]})});
 const result=new Function('$',body.nodes.find(n=>n.name==='Movie Result').parameters.jsCode)($)[0].json;
 a.equal(result.requestKey,'new-request');a.equal(result.searchStarted,true);a.equal(result.repeatRequest,true);
 const render=commit.nodes.find(n=>n.name==='Format Accepted Request').parameters.jsCode;
 const reply=new Function('$','$json',render)(name=>({first:()=>({json:result})}),{error:'Read unavailable'})[0].json;
 a.match(reply.text,/Searching again/);a.match(reply.text,/temporarily unavailable/);a.doesNotMatch(reply.text,/Ready to watch/);
 const status=require('../n8n/status/policy.js');
 const requests=['new-request','older-request'].map(requestKey=>({source:'discord',userId:'111',state:'registered',requestKey,mediaType:'movie',mediaId:'10',title:'Example'}));
 a.deepEqual(status.select(requests,{source:'discord',userId:'111',requestKey:'new-request'})[0].requests.map(r=>r.requestKey),['new-request']);
});

test('season picker stays within Discord limits on middle pages with selections',()=>{
 let r=row();r.mediaJson=JSON.stringify({...JSON.parse(r.mediaJson),seasons:Array.from({length:80},(_,i)=>({seasonNumber:i+1}))});
 r.contextJson=JSON.stringify({seasonPage:2,selectedSeasons:[1,33]});r.state='seasons';const card=p.card(r);
 a.ok(card.choices.length<=25);a.ok(card.choices.some(c=>c.action==='wrong'));a.ok(card.choices.some(c=>c.action==='review'));
 a.equal(p.transition(r,actor('wrong'),Date.now()),'scope');
});
