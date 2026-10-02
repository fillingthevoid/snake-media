function validateProof(p,now){
 if(!p||!Number.isFinite(now)||!['snakeRetentionCoordinatorV1','snakeLockRecoveryV1'].includes(p.workflowId)||!['success','error','canceled','crashed'].includes(p.status)||typeof p.owner!=='string'||! /^[1-9][0-9]{0,15}$/.test(p.owner)||p.activeExecutions!==0)throw Error('Invalid recovery proof');
 const checked=Date.parse(p.checkedAt),stopped=Date.parse(p.stoppedAt);
 if(!Number.isFinite(checked)||!Number.isFinite(stopped)||checked>now+5000||now-checked>30000||checked-stopped<120000)throw Error('Recovery evidence is stale or incomplete');
 return {owner:p.owner,workflowId:p.workflowId,status:p.status,stoppedAt:p.stoppedAt,checkedAt:p.checkedAt};
}
if(typeof module!=='undefined')module.exports={validateProof};
