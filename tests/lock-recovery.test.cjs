const {test}=require('node:test'),a=require('node:assert/strict');
const {validateProof}=require('../n8n/lock-recovery/policy.js');
const now=Date.parse('2026-10-01T10:05:00Z');
const proof={owner:'12',workflowId:'snakeRetentionCoordinatorV1',status:'error',stoppedAt:'2026-10-01T10:00:00Z',checkedAt:'2026-10-01T10:05:00Z',activeExecutions:0};
test('recovery proof requires fresh checks, terminal execution, and cooldown',()=>{
 a.equal(validateProof(proof,now).owner,'12');
 for(const change of [{status:'running'},{activeExecutions:1},{checkedAt:'2026-10-01T10:04:00Z'},{stoppedAt:'2026-10-01T10:04:00Z'},{owner:''},{workflowId:'unrelated'},{checkedAt:'2026-10-01T10:06:00Z'}])a.throws(()=>validateProof({...proof,...change},now));
});
test('native recovery claims expected owner and pauses cleanup before releasing',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const w=JSON.parse(fs.readFileSync(path.join(__dirname,'../n8n/lock-recovery/workflows/Snake Media - Recover Stopped Lock.json'),'utf8'));
 const get=name=>w.nodes.find(n=>n.name===name);
 a.ok(!w.nodes.some(n=>/httpRequest|executeWorkflow|telegram/.test(n.type)));
 a.deepEqual(get('Claim Abandoned Lock').parameters.filters.conditions.map(x=>x.keyName),['key','owner']);
 a.match(get('Claim Abandoned Lock').parameters.filters.conditions[1].keyValue,/json.owner/);
 a.match(get('Release Recovered Lock').parameters.filters.conditions[1].keyValue,/execution.id/);
 let name='Recovery Owns Lock?',sequence=[];
 while(name!=='Recovery Response'){sequence.push(name);name=w.connections[name].main[0][0].node;}
 a.ok(sequence.indexOf('Verify Cleanup Paused')<sequence.indexOf('Release Recovered Lock'));
 a.ok(sequence.indexOf('Verify Recovery Recorded')<sequence.indexOf('Release Recovered Lock'));
 for(const n of w.nodes)if(n.type==='n8n-nodes-base.code')new Function('$','$json','$input','$execution',n.parameters.jsCode);
});
