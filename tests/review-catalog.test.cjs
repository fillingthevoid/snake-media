const {test}=require('node:test'),assert=require('node:assert/strict');
const p=require('../n8n/review-catalog/policy.js');
const now=Date.parse('2026-10-15T20:00:00Z'),body={userId:'10',guildId:'20',channelId:'30',action:'poll'};
const config={source:'discord',state:'review',requestKey:'review:config:20',contextJson:JSON.stringify({kind:'config',guildId:'20',channelId:'40'})};
const auth={body,rows:[config],users:['10','11'],owners:['10'],channels:['30'],now,claimId:'101'};
const root=(entries={})=>({...p.prepareCatalog({...auth,body:{...body,action:'initialize'}}).row,id:7,contextJson:JSON.stringify({kind:'catalog',guildId:'20',entries,cursor:0,lastSync:0})});
const movie={Id:'abc',Type:'Movie',Name:'Turtles',Path:'/data/movies/Turtles/a.mkv',ProviderIds:{Tmdb:'90'},ProductionYear:1990};
const series={Id:'def',Type:'Series',Name:'A show',Path:'/data/tv/A show',ProviderIds:{Tvdb:'91'}};
const page=Items=>[{Items,TotalRecordCount:Items.length}];
const inventory=(extra={})=>p.catalogInventory({state:{entries:{},cursor:0},moviePages:page([movie]),seriesPages:page([series]),movies:[],series:[],health:{checkedAt:now,storage:{guard:true}},now,...extra});
const finish=(r,inv=inventory(),extra={})=>p.finishCatalog({plan:{old:r,body,claimId:'101',needsSync:true,importCursor:'x'},inventory:inv,proofs:[{mediaKey:'tv:91',ok:true,available:true}],now,...extra});

test('only authorized owners initialize or claim the independent native catalog',()=>{
 assert.equal(p.prepareCatalog({...auth,body:{...body,action:'initialize'}}).mode,'insert');
 assert.equal(p.prepareCatalog({...auth,body:{...body,userId:'11',action:'initialize'}}).reply.error,'denied');
 assert.equal(p.prepareCatalog(auth).reply.error,'uninitialized');
 const r=root();assert.equal(p.prepareCatalog({...auth,rows:[config,r]}).mode,'claim');
 assert.equal(p.prepareCatalog({...auth,rows:[config,r,{...r,id:8}]}).reply.error,'duplicate_catalog');
 assert.equal(p.prepareCatalog({...auth,rows:[config,{...r,claimId:'busy',expiresAt:new Date(now+1000).toISOString()}]}).reply.busy,true);
});

test('confirmed retention deletions and recent imports prompt a new targeted reconciliation',()=>{
 const r=root();const state=JSON.parse(r.contextJson);state.lastSync=now-120000;state.importCursor='';r.contextJson=JSON.stringify(state);
 const plan=p.prepareCatalog({...auth,rows:[config,r],deletions:[{key:'file:movie:5:6',updatedAt:new Date(now-1000).toISOString(),payloadJson:JSON.stringify({state:'deleted'})}]});
 assert.equal(plan.needsSync,true);assert.ok(plan.indexingUntil>now);
});

test('inventory verifies complete pages, excludes collections and resolves exact Arr path identities',()=>{
 const show={...series,ProviderIds:{}};
 const inv=inventory({seriesPages:page([show]),series:[{id:5,tvdbId:91,path:'/tv/A show',images:[]}]});
 assert.equal(inv.complete,true);assert.equal(inv.entries['tv:91'].jellyfinId,'def');assert.equal(inv.targets.length,1);
 assert.equal(Object.keys(inventory({moviePages:page([movie,{Type:'BoxSet',Id:'set'}])}).entries).length,2);
 assert.equal(inventory({moviePages:[{Items:[movie],TotalRecordCount:2}]}).complete,false);
 assert.equal(inventory({health:{checkedAt:now,storage:{guard:false}}}).complete,false);
 assert.equal(inventory({health:{checkedAt:now-180000,storage:{guard:true}}}).complete,false);
 const unresolved=inventory({seriesPages:page([show])});assert.equal(unresolved.unresolved.length,1);assert.equal(unresolved.identityComplete,false);
 const ambiguous=inventory({seriesPages:page([show]),series:[{id:5,tvdbId:91,path:'/tv/A show'},{id:6,tvdbId:92,path:'/tv/A show'}]});assert.equal(ambiguous.unresolved.length,1);
});

test('first available file queues zero-vote jobs; real-episode proof is required for series',()=>{
 const r=finish(root());assert.equal(r.reply.jobs.length,2);
 const state=JSON.parse(r.row.contextJson);assert.equal(state.entries['movie:90'].availability.state,'available');
 assert.equal(state.entries['tv:91'].availability.state,'available');
 assert.equal(finish(root(),inventory(),{proofs:[{mediaKey:'tv:91',ok:true,available:false}]}).reply.jobs.length,1);
 assert.equal(finish(root(),inventory(),{proofs:[]}).reply.jobs.length,1);
});

test('two separated successful absences mark removal; failures never imply deletion and reimport restores it',()=>{
 const first=finish(root()),entries=JSON.parse(first.row.contextJson).entries;
 const missing=inventory({state:{entries,cursor:0},moviePages:page([])});
 let r=finish(root(entries),missing);let e=JSON.parse(r.row.contextJson).entries;
 assert.equal(e['movie:90'].availability.state,'available');
 r=finish(root(e),missing,{now:now+15*60000});e=JSON.parse(r.row.contextJson).entries;
 assert.equal(e['movie:90'].availability.state,'unavailable');
 const failed=finish(root(e),{complete:false,error:'library_unavailable'});assert.equal(JSON.parse(failed.row.contextJson).entries['movie:90'].availability.state,'delayed');
 const restored=finish(root(e));assert.equal(JSON.parse(restored.row.contextJson).entries['movie:90'].availability.state,'available');
});

test('publication acknowledgements require the exact lease and do not lose changed pending work',()=>{
 const result=finish(root()),job=result.reply.jobs[0],r={...result.row,id:7};
 const good=p.finishCatalog({plan:{old:r,body:{...body,action:'ack',mediaKey:job.mediaKey,leaseId:job.leaseId,ok:true},claimId:'102',needsSync:false},now});
 assert.equal(good.reply.ok,true);assert.equal(JSON.parse(good.row.contextJson).entries[job.mediaKey].publishedFingerprint,job.fingerprint);
 const stale=p.finishCatalog({plan:{old:r,body:{...body,action:'ack',mediaKey:job.mediaKey,leaseId:'wrong',ok:true},claimId:'102',needsSync:false},now});
 assert.equal(stale.reply.error,'stale_job');
 const retry=finish(r,inventory(),{now:now+1000});assert.equal(retry.reply.jobs.length,0);
});

test('bounded checking rotates the cursor and unresolved identities prevent false absence',()=>{
 const many=Array.from({length:75},(_,i)=>({...movie,Id:'m'+i,ProviderIds:{Tmdb:String(i+100)}}));
 const inv=inventory({moviePages:page(many),seriesPages:page([])});assert.equal(inv.checkedKeys.length,50);assert.equal(inv.nextCursor,50);
 const next=inventory({state:{entries:{},cursor:50},moviePages:page(many),seriesPages:page([])});assert.equal(next.checkedKeys.length,50);assert.notDeepEqual(next.checkedKeys,inv.checkedKeys);
 const first=finish(root());const entries=JSON.parse(first.row.contextJson).entries;
 const unresolved=inventory({state:{entries,cursor:0},moviePages:page([{...movie,ProviderIds:{},Path:'/unmatched/file.mkv'}])});
 const later=finish(root(entries),unresolved,{now:now+3600000});assert.notEqual(JSON.parse(later.row.contextJson).entries['movie:90'].availability.state,'unavailable');
});

test('jobs are capped at ten, delayed after failure, and unchanged acknowledged entries are not reposted',()=>{
 const movies=Array.from({length:15},(_,i)=>({...movie,Id:'m'+i,ProviderIds:{Tmdb:String(i+100)}}));
 const inv=inventory({moviePages:page(movies),seriesPages:page([])}),r=finish(root(),inv);assert.equal(r.reply.jobs.length,10);
 const j=r.reply.jobs[0];let record={...r.row,id:7};
 const ack=p.finishCatalog({plan:{old:record,body:{...body,action:'ack',mediaKey:j.mediaKey,leaseId:j.leaseId,ok:false,error:'missing_post'},claimId:'ack',needsSync:false},now});
 const retry=finish({...ack.row,id:7},inv,{now:now+1000});assert.ok(!retry.reply.jobs.some(x=>x.mediaKey===j.mediaKey));
});

test('existing review backend can bind a catalog title with zero votes and shows catalog availability',()=>{
 const reviews=require('../n8n/media-reviews/policy.js');
 const catalog={...finish(root()).row,id:7};
 const input={body:{...body,op:'summary',mediaKey:'movie:90'},rows:[config,catalog],notices:[],requests:[],users:['10','11'],owners:['10'],channels:['30'],now};
 let r=reviews.reviewOperation(input);assert.equal(r.reply.ok,true);assert.equal(r.reply.total,0);assert.equal(r.row,null);assert.equal(r.reply.availability.state,'available');
 assert.equal(reviews.reviewOperation({...input,body:{...input.body,userId:'11'}}).reply.ok,false);
 r=reviews.reviewOperation({...input,body:{...input.body,op:'bind',messageId:'70',messageChannelId:'60',threadId:'60'}});
 assert.equal(r.reply.total,0);assert.equal(JSON.parse(r.row.contextJson).kind,'post');
});

test('unresolved metadata is retained but cannot overwhelm the bounded delivery response',()=>{
 const r=root(),state=JSON.parse(r.contextJson);state.unresolved=Array.from({length:500},()=>({title:'Unmatched title',reason:'missing_identity'}));r.contextJson=JSON.stringify(state);
 const result=p.finishCatalog({plan:{old:r,body,claimId:'x',needsSync:false},now});
 assert.equal(result.reply.unresolved.length,25);assert.equal(result.reply.unresolvedCount,500);assert.equal(JSON.parse(result.row.contextJson).unresolved.length,500);
});
