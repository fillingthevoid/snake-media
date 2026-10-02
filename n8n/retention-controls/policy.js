// Confirmation and immutable retention amendments. No service calls.
function parseChange(text){
 if(typeof text!=='string')return null;
 const input=text.trim();if(!/^\/?(?:extend|keep)(?:@[A-Za-z0-9_]+)?(?:\s|$)/i.test(input))return null;
 let m=input.match(/^\/?extend(?:@[A-Za-z0-9_]+)?\s+(.+?)\s+([0-9]+)\s+days?$/i);
 if(m&&Number(m[2])>=1&&Number(m[2])<=3650)return {operation:'extend',query:m[1].trim(),days:Number(m[2])};
 m=input.match(/^\/?keep(?:@[A-Za-z0-9_]+)?\s+(.+?)\s+permanently$/i);
 if(m)return {operation:'permanent',query:m[1].trim()};
 return {error:'Use extend <title> 7 days (1–3650 whole days), or keep <title> permanently.'};
}
function prepareChange(actor,rows){
 if(!['discord','telegram'].includes(actor.source)||typeof actor.userId!=='string'||!/^\d+$/.test(actor.userId))throw Error('Invalid actor');
 const parsed=parseChange(actor.text);if(!parsed||parsed.error)return {notice:parsed?.error||'Not a retention command.'};
 const matches=rows.filter(r=>r.source===actor.source&&r.userId===actor.userId&&r.userId!=='1'&&r.state==='registered'&&r.requestKey&&(!actor.requestKey||r.requestKey===actor.requestKey)&&['movie','tv'].includes(r.mediaType)&&/^\d+$/.test(String(r.mediaId))&&String(r.title).toLowerCase().includes(parsed.query.toLowerCase()));
 const keys=new Set(matches.map(r=>r.mediaType+':'+r.mediaId));
 if(!matches.length)return {notice:'No requests of yours match that title on this platform.'};
 if(keys.size!==1)return {notice:'Several matches. Please use a more specific title:\n'+[...new Set(matches.map(r=>r.title))].slice(0,8).map(t=>'• '+String(t).slice(0,100)).join('\n')};
 const r=matches[0];return {change:{...parsed,source:actor.source,userId:actor.userId,requestKeys:[...new Set(matches.map(r=>r.requestKey))],mediaType:r.mediaType,mediaId:String(r.mediaId),title:String(r.title).slice(0,150)}};
}
function planChange(change,requests,decisions,records,{pendingId,now}){
 if(!['extend','permanent'].includes(change.operation)||!Array.isArray(change.requestKeys)||!change.requestKeys.length||!/^\d+$/.test(String(pendingId))||!Number.isFinite(now))throw Error('Invalid amendment');
 if(change.operation==='extend'&&(!Number.isInteger(change.days)||change.days<1||change.days>3650))throw Error('Invalid duration');
 const selected=change.requestKeys.map(key=>requests.find(r=>r.requestKey===key));
 if(selected.some(r=>!r||r.state!=='registered'||r.mediaType!==change.mediaType||String(r.mediaId)!==change.mediaId||r.source!==change.source||r.userId!==change.userId))throw Error('Request ownership changed');
 const existing=records.filter(r=>r.key==='change:'+pendingId);
 if(existing.length>1)throw Error('Duplicate amendment');
 if(existing.length){const e=JSON.parse(existing[0].payloadJson);if(e.source!==change.source||e.userId!==change.userId||e.operation!==change.operation||e.mediaId!==change.mediaId||e.mediaType!==change.mediaType)throw Error('Amendment collision');return e;}
 const result={version:1,pendingId:String(pendingId),operation:change.operation,source:change.source,userId:change.userId,requestKeys:change.requestKeys,mediaType:change.mediaType,mediaId:change.mediaId,title:change.title,createdAt:new Date(now).toISOString(),files:[]};
 if(change.operation==='permanent')return result;
 const ids=new Set(selected.flatMap(r=>JSON.parse(r.episodeIdsJson||'[]').map(String)));
 for(const row of records)if(selected.some(r=>row.key==='request:'+r.requestKey))for(const id of JSON.parse(row.payloadJson).episodeIds||[])ids.add(String(id));
 for(const d of decisions){
  if(change.mediaType==='tv'&&!(d.episodeIds||[]).some(id=>ids.has(String(id))))continue;
  if(d.state!=='tracked'||d.identityProtected||!d.expiresAt||!Number.isFinite(Date.parse(d.expiresAt))||!Number.isFinite(Date.parse(d.importedAt))||!Number.isSafeInteger(d.fileId)||typeof d.path!=='string')continue;
  const minimumExpiry=new Date(Math.max(now,Date.parse(d.expiresAt))+change.days*86400000).toISOString();
  result.files.push({fileId:d.fileId,path:d.path,importedAt:d.importedAt,minimumExpiry});
 }
 if(!result.files.length)return {notice:'No imported files with a timed expiry need extending. Files already protected stay protected; upcoming episodes keep their existing retention.'};
 return result;
}
function changeCard(row){
 if(row.version)return row;
 const c=JSON.parse(row.contextJson).retentionChange;
 if(!c)return null;
 if(row.state==='cancelled')return {version:1,status:'notice',text:'Cancelled. Retention was not changed.'};
 if(row.state!=='preview'||Date.parse(row.expiresAt)<=Date.now())return {version:1,status:'notice',text:'This retention choice expired or was already handled. Send a new command.'};
 const text=(c.mediaType==='tv'?'📺 ':'🎬 ')+c.title+'\n\n'+(c.operation==='permanent'?'Keep your requests for this title permanently, including future episodes attached to them?':`Add ${c.days} days to each currently imported eligible file’s effective expiry (or now, if later)?\nWatching cannot shorten this extension. Upcoming episodes keep their existing retention.`)+'\n\nNo media will be re-downloaded.';
 return {version:1,status:'confirmation',text,pendingId:String(row.id),choices:[{label:'Confirm',action:'confirm'},{label:'Cancel',action:'cancel'}]};
}
if(typeof module!=='undefined')module.exports={parseChange,prepareChange,planChange,changeCard};
