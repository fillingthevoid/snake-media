const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root=__dirname+'/../n8n/retention/workflows/';
function workflow(name){return JSON.parse(fs.readFileSync(root+'Snake Media - '+name+'.json'));}
function run(w,node,json,refs={},rows=[json]){
 const code=w.nodes.find(n=>n.name===node).parameters.jsCode;
 return JSON.parse(JSON.stringify(vm.runInNewContext('(function(){'+code+'})()',{$json:json,$input:{first:()=>({json}),all:()=>rows.map(json=>({json}))},$:name=>({first:()=>({json:refs[name]})}),Date})));
}
test('confirmation displays defaults, permanent override and subscription before commit',()=>{
 const w=workflow('Preview Media');
 for(const [mediaType,days,expected] of [['movie',7,/7 days/],['tv',30,/30 days/],['movie',null,/permanently/]]){
  const row={id:1,state:'preview',expiresAt:'2099-01-01',mediaType,mediaJson:JSON.stringify({title:'Example',overview:'Overview'}),contextJson:JSON.stringify({retentionPolicy:{version:2,days}})};
  const out=run(w,'Render Preview',row)[0].json;
  assert.match(out.text,expected);assert.equal(out.choices[0].action,'confirm');
  if(mediaType==='tv')assert.match(out.text,/future seasons will be monitored/);
 }
});
test('delete workflow refuses changed file identity, monitoring failure and unknown HTTP outcomes',()=>{
 const w=workflow('Delete Expired File');
 const d={owner:'1',key:'file:movie:9:10',fileId:10,path:'/movies/a.mkv',importedAt:'2026-01-01',mediaType:'movie',mediaId:'9'};
 assert.throws(()=>run(w,'Validate File Identity',{id:11,path:d.path,dateAdded:d.importedAt},{'Deletion Input':d}));
 assert.throws(()=>run(w,'Verify Unmonitor And Coverage',{monitored:true,movieFile:{id:10,path:d.path}},{'Deletion Input':d}));
 for(const statusCode of [400,401,403,429,500,undefined])assert.throws(()=>run(w,'Check Delete Response',{statusCode},{'Deletion Input':d}));
 assert.throws(()=>run(w,'Build Deleted Record',{statusCode:200},{'Deletion Input':d}));
 assert.equal(JSON.parse(run(w,'Build Deleted Record',{statusCode:404},{'Deletion Input':d})[0].json.payloadJson).state,'deleted');
});
test('commit saves the confirmed retention policy and includes unaired eligible episodes',()=>{
 const w=workflow('Commit Media Under Lock');
 const context={retentionPolicy:{days:30},requestedAt:'2026-01-01T00:00:00.000Z'};
 const refs={'Confirmed Metadata':{context,choice:'latest'},'Series Identity':{id:3,tvdbId:4,title:'Show'}};
 const episodes=[{id:10,seasonNumber:1,episodeNumber:1,airDateUtc:'2020-01-01',episodeFileId:0},{id:11,seasonNumber:2,episodeNumber:1,airDateUtc:'2099-01-01',episodeFileId:0}];
 const out=run(w,'Selected Episode Snapshot',episodes[0],refs,episodes)[0].json;
 assert.equal(out.retentionDays,30);assert.equal(out.retentionExplicit,true);
 assert.deepEqual(out.episodeIds,['10','11']);assert.deepEqual(out.missingIds,[10]);
});
test('missing episode metadata returns a notice so the coordinator can release its lock',()=>{
 const w=workflow('Commit Media Under Lock');
 const refs={'Confirmed Metadata':{context:{retentionPolicy:{days:30}},choice:'latest'},'Series Identity':{id:3,tvdbId:4,title:'Show'}};
 const out=run(w,'Selected Episode Snapshot',{},refs,[{}])[0].json;
 assert.equal(out.status,'notice');assert.match(out.text,/metadata/);
});

test('search plans read saved tracking and subscription after intermediate nodes change payload',()=>{
 const w=workflow('Commit Media Under Lock');
 for(const [kind,snap] of [['Movie','Movie Snapshot'],['TV','Selected Episode Snapshot']]){
  const snapshot={mediaId:'8',missing:true,missingIds:[10]};
  const refs={[snap]:snapshot,['Register '+kind+' Before Search']:{requestKey:'discord:2:3'},['Save '+kind+' Subscription']:{key:'request:discord:2:3'}};
  assert.deepEqual(run(w,kind+' Search Plan',{id:10,monitored:true},refs)[0].json,snapshot);
  refs['Save '+kind+' Subscription']={key:'request:wrong'};
  assert.throws(()=>run(w,kind+' Search Plan',{},refs));
 }
});

test('only a successfully claimed action authorizes editing the Discord card',()=>{
 const w=workflow('Confirm Media');
 for(const [valid,claim,accepted] of [[false,null,false],[true,{},false],[true,{actionAccepted:true},true]]){
  const refs={'Validate Action':valid?{row:{id:12}}:{},'Verify Claim':claim};
  assert.equal(run(w,'Mark Accepted Action',{version:1,status:'notice',text:'Result'},refs)[0].json.actionAccepted,accepted);
 }
});
