const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const workflows=JSON.parse(fs.readFileSync(__dirname+'/../config-templates/n8n-current-media-workflows.json','utf8'));
function run(id,name,input,refs={}){
 const node=workflows.find(w=>w.id===id).nodes.find(n=>n.name===name);
 const data=Array.isArray(input)?input:[input];
 const inputApi={all:()=>data.map(json=>({json})),first:()=>({json:data[0]})};
 const dollar=name=>({first:()=>({json:refs[name]}),all:()=>refs[name].map(json=>({json}))});
 return new Function('$json','$input','$','$execution',node.parameters.jsCode)(data[0],inputApi,dollar,{id:'claim'}).map(x=>x.json);
}
const actor={source:'discord',userId:'111',destinationId:'333',messageId:'444',requestedAt:new Date().toISOString(),text:'add Example'};
test('embedded preview deduplicates candidates and claims persist the selected identity',()=>{
 const lookup=[{tmdbId:1,title:'Example',year:1999},{tmdbId:1,title:'Duplicate',year:1999},{tmdbId:2,title:'Example II',year:2000}];
 let row=run('snakePreviewMediaV1','Select Preview',lookup,{'Preview Input':{mediaType:'movie',title:'Example',context:actor}})[0];row.id=5;
 assert.equal(JSON.parse(row.contextJson).titleMatches.items.length,2);
 let plan=run('snakeConfirmMediaV1','Validate Action',row,{'Action Input':{...actor,action:'wrong'}})[0];
 assert.equal(plan.row.state,'preview');assert.equal(plan.state,'preview');
 row={...plan.row,state:plan.state,choice:plan.choice,claimId:plan.claimId};
 const card=run('snakeConfirmMediaV1','Render Choice',row)[0];assert.equal(card.menuChoices[0].action,'request');
 plan=run('snakeConfirmMediaV1','Validate Action',row,{'Action Input':{...actor,action:'match_1'}})[0];
 assert.equal(JSON.parse(plan.row.mediaJson).tmdbId,2);assert.equal(plan.state,'preview');
 row={...plan.row,state:plan.state,choice:plan.choice,claimId:plan.claimId};
 assert.equal(run('snakeConfirmMediaV1','Validate Action',row,{'Action Input':{...actor,action:'confirm'}})[0].state,'processing');
});
test('embedded expiry Back renders durations and cannot enter media processing',()=>{
 const r=require('../n8n/retention-controls/policy.js');
 const guide=r.prepareChange({...actor,text:'extend'},[{...actor,state:'registered',requestKey:'r1',mediaType:'movie',mediaId:'9',title:'Example'}]).guide;
 let row={id:5,...actor,state:'preview',expiresAt:new Date(Date.now()+300000).toISOString(),claimId:'old',contextJson:JSON.stringify({retentionGuide:{...guide,selected:0}}),mediaType:'movie',mediaJson:'{"title":"Example"}'};
 let plan=run('snakeConfirmMediaV1','Validate Action',row,{'Action Input':{...actor,action:'retdays_7'}})[0];
 row={...plan.row,state:plan.state};assert.ok(JSON.parse(row.contextJson).retentionChange);
 plan=run('snakeConfirmMediaV1','Validate Action',row,{'Action Input':{...actor,action:'retback'}})[0];
 assert.equal(plan.state,'preview');row={...plan.row,state:plan.state};
 const card=run('snakeConfirmMediaV1','Render Choice',row)[0];assert.equal(card.choices[0].action,'retdays_7');assert.ok(!card.choices.some(c=>c.action==='wrong'));
});
test('Telegram dynamic poster data retains title choices and correction prompt together',()=>{
 const input={pendingId:'5',posterUrl:'https://image.tmdb.org/t/p/w500/example.jpg',choices:[{label:'Example',action:'match_0'},{label:'Back',action:'back'},{label:'Cancel',action:'cancel'}],menuChoices:[{label:'Correct search',action:'request'}]};
 const output=run('snakeTelegramCardV1','Recommendation Card Data',input)[0];
 assert.deepEqual(output.keyboard.rows.flatMap(r=>r.row.buttons).map(b=>b.additionalFields.callback_data),['snake:5:match_0','snake:5:back','snake:5:cancel','snake_menu:request']);
 assert.equal(output.posterUrl,input.posterUrl);
});

for(const source of ['discord','telegram'])test(source+' embedded multi-season picker persists selections and scopes one subscription',()=>{
 let row={id:5,...actor,source,state:'scope',choice:'',claimId:'old',expiresAt:'2099-01-01',mediaType:'tv',mediaJson:JSON.stringify({title:'Example',tvdbId:10,seasons:[{seasonNumber:1},{seasonNumber:2},{seasonNumber:3}]}),contextJson:'{}'};
 function click(action){const plan=run('snakeConfirmMediaV1','Validate Action',row,{'Action Input':{...actor,source,action}})[0];assert.ok(plan.state);row={...plan.row,state:plan.state,choice:plan.choice,claimId:plan.claimId};return run('snakeConfirmMediaV1','Render Choice',row)[0];}
 click('choose');click('season_1');const card=click('season_3');assert.equal(row.state,'seasons');assert.match(card.text,/Seasons 1, 3/);
 const tg=run('snakeTelegramCardV1','Recommendation Card Data',card)[0];assert.ok(tg.keyboard.rows.flatMap(r=>r.row.buttons).some(b=>b.additionalFields.callback_data==='snake:5:review'));
 click('review');assert.equal(row.choice,'seasons_1_3');click('back');assert.equal(row.state,'seasons');click('review');
 const n=workflows.find(w=>w.id==='snakeCommitMediaBodyV2').nodes.find(n=>n.name==='Selected Episode Snapshot');
 const code=n.parameters.jsCode.split('if(typeof module')[0];const subscription=new Function(code+';return subscription;')();
 const episodes=[1,2,3].map(s=>({id:s,seasonNumber:s,airDateUtc:'2020-01-01'}));assert.deepEqual(subscription(episodes,row.choice,Date.now()).selectedSeasons,[1,3]);
});
