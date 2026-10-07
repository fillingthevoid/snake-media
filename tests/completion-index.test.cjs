const test=require('node:test'),assert=require('node:assert/strict');
const {completionMarkers,pendingBatches,retireChoice}=require('../n8n/maintenance/policy.js');
const request={requestKey:'discord:2:3:4',source:'discord',userId:'2',destinationId:'3',state:'registered',mediaType:'tv',mediaId:'8',baselineCaptured:true};
test('completion index retires only proven first notices and retains future episode claims',()=>{
 const r={...request,episodeIdsJson:'[1,2]',retentionDays:30};
 const notice={requestKey:r.requestKey,source:'discord',destinationId:'3',notificationKey:r.requestKey+':tv-ready',state:'pending',createdAt:'2026-10-01T00:00:00Z'};
 assert.equal(completionMarkers([r],[notice],[])[0].state,'complete');
 assert.equal(r.state,'registered');assert.equal(r.episodeIdsJson,'[1,2]');
 for(const bad of [{...notice,state:'failed'},{...notice,source:'telegram'},{...notice,destinationId:'9'},{...notice,notificationKey:r.requestKey+':progress:downloading'}])
  assert.equal(completionMarkers([r],[bad],[])[0].state,'pending');
});
test('choice compaction preserves live choices and every processing operation',()=>{
 const now=Date.parse('2026-10-06T00:00:00Z');
 const old={state:'preview',expiresAt:'2026-09-01T00:00:00Z',updatedAt:'2026-09-01T00:00:00Z',contextJson:'private payload',mediaJson:'large poster metadata'};
 assert.equal(retireChoice(old,now).state,'expired');assert.equal(retireChoice(old,now).contextJson,'{}');
 assert.equal(retireChoice({...old,state:'processing'},now),null);
 assert.equal(retireChoice({...old,expiresAt:'2026-10-07T00:00:00Z'},now),null);
 assert.equal(retireChoice({...old,state:'done',updatedAt:'2026-01-01T00:00:00Z'},now).mediaJson,'{}');
 assert.equal(retireChoice({...old,state:'done'},now),null);
});
test('reconciliation never resets a completed marker and active batches exclude completed requests',()=>{
 const markers=completionMarkers([request],[],[{requestKey:request.requestKey,state:'complete'}]);
 assert.equal(markers[0].state,'complete');assert.deepEqual(pendingBatches(markers),[]);
 const pending=completionMarkers([request],[],[]);
 assert.deepEqual(pendingBatches(pending),[{keys:[request.requestKey]}]);
 assert.deepEqual(completionMarkers([{...request,userId:'1'},{...request,baselineCaptured:false}],[],[]),[]);
});
