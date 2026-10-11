// Refresh a collected group while its coordinator owns the mutation lock.
function freshGroup(input,requests,records,mode,now){
 const first=input?.requests?.[0];
 if(!input||!first||!['movie','tv'].includes(first.mediaType)||!/^[1-9][0-9]{0,15}$/.test(String(first.mediaId))||!/^[1-9][0-9]{0,15}$/.test(input.owner||'')||!['preview','enabled'].includes(mode)||!Number.isFinite(now)||!Array.isArray(requests)||!Array.isArray(records)||!Array.isArray(input.watched)||!Array.isArray(input.sessions))throw Error('Invalid retention group');
 const claimed=requests.filter(r=>r.requestKey);
 if(claimed.some(r=>r.mediaType!==first.mediaType||String(r.mediaId)!==String(first.mediaId)))throw Error('Retention group identity changed');
 const age=now-Date.parse(input.snapshotAt);
 const base={...input,mode,requests:claimed.filter(r=>r.state==='registered'&&r.userId!=='1'),records:records.filter(r=>r.key)};
 if(!Number.isFinite(age)||age<0||age>300000)return {...base,deferred:true,reason:'snapshot_expired'};
 if(!base.requests.length)return {...base,deferred:true,reason:'no_current_claims'};
 return base;
}
if(typeof module!=='undefined')module.exports={freshGroup};
