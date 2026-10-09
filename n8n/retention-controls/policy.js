// Confirmation and immutable retention amendments. No service calls.
const usabilityEvidence=require('../request-usability/evidence.js');
function parseChange(text){
 if(typeof text!=='string')return null;
 const input=text.trim();if(!/^\/?(?:extend|keep)(?:@[A-Za-z0-9_]+)?(?:\s|$)/i.test(input))return null;
 const bare=input.match(/^\/?(extend|keep)(?:@[A-Za-z0-9_]+)?$/i);
 if(bare)return {operation:bare[1].toLowerCase()==='keep'?'permanent':'extend',guided:true};
 let m=input.match(/^\/?extend(?:@[A-Za-z0-9_]+)?\s+(.+?)\s+([0-9]+)\s+days?$/i);
 if(m&&Number(m[2])>=1&&Number(m[2])<=3650)return {operation:'extend',query:m[1].trim(),days:Number(m[2])};
 m=input.match(/^\/?keep(?:@[A-Za-z0-9_]+)?\s+(.+?)\s+permanently$/i);
 if(m)return {operation:'permanent',query:m[1].trim()};
 return {error:'Use extend <title> 7 days (1–3650 whole days), or keep <title> permanently.'};
}
function titleKey(text){
 return String(text).normalize('NFKD').replace(/\p{M}/gu,'').toLowerCase()
  .replace(/&/g,' and ').replace(/['’]/g,'').replace(/[^\p{L}\p{N}]+/gu,' ').trim();
}
function prepareChange(actor,rows,records=[],now=Date.now()){
 if(!['discord','telegram'].includes(actor.source)||typeof actor.userId!=='string'||!/^\d+$/.test(actor.userId))throw Error('Invalid actor');
 const parsed=parseChange(actor.text);if(!parsed||parsed.error)return {notice:parsed?.error||'Not a retention command.'};
 const owned=rows.filter(r=>r.source===actor.source&&r.userId===actor.userId&&r.userId!=='1'&&r.state==='registered'&&r.requestKey&&(!actor.requestKey||r.requestKey===actor.requestKey)&&(!actor.mediaId||(r.mediaType===actor.mediaType&&String(r.mediaId)===actor.mediaId))&&['movie','tv'].includes(r.mediaType)&&/^\d+$/.test(String(r.mediaId))&&typeof r.title==='string'&&r.title.trim());
 const query=titleKey(parsed.query||'');
 let matches=parsed.guided?owned:query?owned.filter(r=>titleKey(r.title).includes(query)):[];
 if(!parsed.guided&&matches.some(r=>titleKey(r.title)===query))matches=matches.filter(r=>titleKey(r.title)===query);
 const keys=new Set(matches.map(r=>r.mediaType+':'+r.mediaId));
 if(!matches.length)return {notice:'No requests of yours match that title on this platform.'};
 if(parsed.guided||keys.size!==1){
  const candidates=[...keys].map(key=>{const rs=matches.filter(r=>r.mediaType+':'+r.mediaId===key),r=rs[0];return {source:actor.source,userId:actor.userId,mediaType:r.mediaType,mediaId:String(r.mediaId),title:r.title.slice(0,150),requestKeys:[...new Set(rs.map(r=>r.requestKey))],expiryFiles:usabilityEvidence.scopedFiles(rs,records,now).map(f=>({expiresAt:f.expiresAt,checkedAt:f.checkedAt,identityProtected:f.identityProtected}))};});
  candidates.sort((a,b)=>a.title.localeCompare(b.title)||a.mediaId.localeCompare(b.mediaId));
  if(actor.mediaId&&candidates.length===1){
   if(parsed.operation==='permanent')return {change:{...candidates[0],operation:'permanent'}};
   return {guide:{operation:'extend',candidates,page:0,selected:0}};
  }
  return {guide:{operation:parsed.operation,...(parsed.days?{days:parsed.days}:{}),candidates,page:0}};
 }
 const r=matches[0];return {change:{...parsed,source:actor.source,userId:actor.userId,requestKeys:[...new Set(matches.map(r=>r.requestKey))],mediaType:r.mediaType,mediaId:String(r.mediaId),title:String(r.title).slice(0,150),expiryFiles:usabilityEvidence.scopedFiles(matches,records,now).map(f=>({expiresAt:f.expiresAt,checkedAt:f.checkedAt,identityProtected:f.identityProtected}))}};
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
function guideAction(row,actor,now){
 if(!row||['source','userId','destinationId'].some(k=>row[k]!==actor[k]))throw Error('Not your request');
 if(row.state!=='preview'||!Number.isFinite(Date.parse(row.expiresAt))||Date.parse(row.expiresAt)<=now)throw Error('Expired or handled');
 const ctx=JSON.parse(row.contextJson);let g=ctx.retentionGuide;
 if(actor.action==='retback'&&ctx.retentionChange){
  g=ctx.retentionReturn||{operation:ctx.retentionChange.operation,candidates:[ctx.retentionChange],page:0,selected:0};
  delete g.days;if(g.operation==='permanent')delete g.selected;delete ctx.retentionChange;delete ctx.retentionReturn;ctx.retentionGuide=g;
  return {state:'preview',choice:'retback',contextJson:JSON.stringify(ctx)};
 }
 if(!g||!Array.isArray(g.candidates)||!['extend','permanent'].includes(g.operation))throw Error('Invalid guide');
 if(actor.action==='cancel')return {state:'cancelled',choice:'cancel',contextJson:row.contextJson};
 const page=actor.action.match(/^retpage_([0-9]{1,3})$/),title=actor.action.match(/^rettitle_([0-9]{1,4})$/);
 if(actor.action==='retback'&&g.selected!==undefined){delete g.selected;delete g.days;}
 else if(page&&g.selected===undefined&&Number(page[1])*8<g.candidates.length)g.page=Number(page[1]);
 else if(title&&g.selected===undefined&&Number(title[1])>=g.page*8&&Number(title[1])<(g.page+1)*8&&g.candidates[Number(title[1])])g.selected=Number(title[1]);
 else if(/^retdays_(7|30)$/.test(actor.action)&&g.selected!==undefined&&g.operation==='extend'&&!g.days)g.days=Number(actor.action.slice(8));
 else throw Error('Stale or invalid guide choice');
 if(g.selected!==undefined&&(g.operation==='permanent'||g.days)){
  ctx.retentionReturn=JSON.parse(JSON.stringify(g));ctx.retentionChange={...g.candidates[g.selected],operation:g.operation,...(g.operation==='extend'?{days:g.days}:{})};delete ctx.retentionGuide;
 }
 return {state:'preview',choice:actor.action,contextJson:JSON.stringify(ctx)};
}
function changeCard(row){
 if(row.version)return row;
 const ctx=JSON.parse(row.contextJson),c=ctx.retentionChange,g=ctx.retentionGuide;
 if(!c&&!g)return null;
 if(row.state==='cancelled')return {version:1,status:'notice',text:'Cancelled. Retention was not changed.'};
 if(row.state!=='preview'||Date.parse(row.expiresAt)<=Date.now())return {version:1,status:'notice',text:'This retention choice expired or was already handled. Send a new command.'};
 if(g){
  let text,choices;
  if(g.selected===undefined){
   text='Choose one of your requested titles to '+(g.operation==='permanent'?'keep permanently.':'extend.');
   choices=g.candidates.slice(g.page*8,g.page*8+8).map((r,i)=>({label:((r.mediaType==='tv'?'TV: ':'Movie: ')+r.title).slice(0,80),action:'rettitle_'+(g.page*8+i)}));
   if(g.page>0)choices.push({label:'Previous',action:'retpage_'+(g.page-1)});
   if((g.page+1)*8<g.candidates.length)choices.push({label:'Next',action:'retpage_'+(g.page+1)});
  }else{text=g.candidates[g.selected].title+'\nHow much time would you like to add?\nFor a custom duration, send /extend <title> <days> days.';choices=[{label:'Extend by 7 days',action:'retdays_7'},{label:'Extend by 30 days',action:'retdays_30'},{label:'Back',action:'retback'}];}
  choices.push({label:'Cancel',action:'cancel'});
  return {version:1,status:'confirmation',text,pendingId:String(row.id),choices};
 }
 const text=(c.mediaType==='tv'?'📺 ':'🎬 ')+c.title+'\n\n'+(c.operation==='permanent'?'Keep your requests for this title permanently, including future episodes attached to them?':`Extend by ${c.days} days?\n`+usabilityEvidence.expiryPreview(c,c.expiryFiles,Date.now())+'\nWatching cannot shorten this extension. Upcoming episodes keep their existing retention.')+'\n\nNo media will be re-downloaded.';
 const choices=[{label:'Confirm',action:'confirm'}];if(ctx.retentionReturn||c.requestKeys?.length)choices.push({label:'Back',action:'retback'});choices.push({label:'Cancel',action:'cancel'});
 return {version:1,status:'confirmation',text,pendingId:String(row.id),choices};
}
if(typeof module!=='undefined')module.exports={parseChange,prepareChange,planChange,changeCard,guideAction,titleKey};
