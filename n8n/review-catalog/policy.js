// Durable review catalog decisions. No media writes or media-request lock.
const CATALOG_INTERVAL=15*60000;
function catalogId(x){return typeof x==='string'&&/^[1-9][0-9]{0,19}$/.test(x)&&BigInt(x)<2n**64n;}
function catalogRecord(body,state){return {source:'discord',userId:body.userId,destinationId:body.channelId,requestKey:'review:catalog:'+body.guildId,contextJson:JSON.stringify(state),mediaType:'',mediaJson:'{}',state:'review',claimId:'',choice:'',expiresAt:'2099-01-01T00:00:00.000Z'};}
function prepareCatalog({body,rows,events=[],deletions=[],users,owners,channels,now,claimId}){
 const fail=error=>({mode:'read',reply:{version:1,ok:false,error}});
 if(!body||![body.userId,body.guildId,body.channelId].every(catalogId)||!users.includes(body.userId)||!owners.includes(body.userId)||!channels.includes(body.channelId))return fail('denied');
 if(!['initialize','poll','ack'].includes(body.action)||!Array.isArray(rows))return fail('invalid_operation');
 const key='review:catalog:'+body.guildId,roots=rows.filter(r=>r.source==='discord'&&r.state==='review'&&r.requestKey===key);
 if(roots.length>1)return fail('duplicate_catalog');
 const config=rows.filter(r=>r.requestKey==='review:config:'+body.guildId&&r.source==='discord'&&r.state==='review');
 if(config.length!==1)return fail('unconfigured');
 let destination;try{destination=JSON.parse(config[0].contextJson).channelId;}catch{return fail('invalid_snapshot');}
 if(!catalogId(destination))return fail('unconfigured');
 if(!roots.length){
  if(body.action!=='initialize')return fail('uninitialized');
  const entries={};
  for(const r of rows){if(r.source!=='discord'||r.state!=='review')continue;let d;try{d=JSON.parse(r.contextJson);}catch{return fail('invalid_snapshot');}
   if(d.kind==='post'&&d.guildId===body.guildId&&/^(movie|tv):[1-9][0-9]{0,19}$/.test(d.mediaKey))entries[d.mediaKey]={mediaKey:d.mediaKey,mediaType:d.mediaKey.split(':')[0],title:d.title,posterUrl:d.posterUrl||null,knownPost:true};}
  return {mode:'insert',row:catalogRecord(body,{kind:'catalog',guildId:body.guildId,entries,cursor:0,lastSync:0,importCursor:'',unresolved:[]}),reply:{version:1,ok:true,initialized:true}};
 }
 const old=roots[0];let state;try{state=JSON.parse(old.contextJson);}catch{return fail('invalid_snapshot');}
 if(!state||state.kind!=='catalog'||state.guildId!==body.guildId||!state.entries||typeof state.entries!=='object'||Array.isArray(state.entries))return fail('invalid_snapshot');
 if(body.action==='initialize')return {mode:'read',reply:{version:1,ok:true,initialized:true}};
 if(old.claimId&&Date.parse(old.expiresAt)>now)return {mode:'read',reply:{version:1,ok:true,busy:true,jobs:[]}};
 const imported=events.filter(e=>e.state==='imported'&&Date.parse(e.receivedAt)<=now+60000).sort((a,b)=>Date.parse(b.receivedAt)-Date.parse(a.receivedAt))[0];
 const deleted=deletions.filter(r=>{try{return JSON.parse(r.payloadJson).state==='deleted'&&Date.parse(r.updatedAt)<=now;}catch{return false;}}).sort((a,b)=>Date.parse(b.updatedAt)-Date.parse(a.updatedAt))[0];
 const importCursor=(imported?String(imported.eventKey)+':'+imported.receivedAt:'')+'|deleted:'+(deleted?deleted.key+':'+deleted.updatedAt:'');
 const indexingUntil=Math.max(imported?Date.parse(imported.receivedAt)+30*60000:0,deleted?Date.parse(deleted.updatedAt)+30*60000:0,state.indexingUntil||0);
 const needsSync=body.action==='poll'&&(!state.lastSync||now-state.lastSync>=CATALOG_INTERVAL||indexingUntil>now&&now-state.lastSync>=5*60000||importCursor!==state.importCursor&&now-state.lastSync>=60000);
 return {mode:'claim',old,body,claimId:String(claimId),destination,needsSync,importCursor,indexingUntil,row:{...old,claimId:String(claimId),expiresAt:new Date(now+6*60000).toISOString()}};
}
function catalogPages(pages){
 if(!Array.isArray(pages)||!pages.length)throw Error('library_unavailable');
 let rows=[],total=null;
 for(const page of pages){const p=page?.body||page;if(page?.statusCode&&page.statusCode!==200||!Array.isArray(p?.Items)||!Number.isSafeInteger(p.TotalRecordCount)||p.TotalRecordCount<0)throw Error('library_unavailable');
  if(total!==null&&total!==p.TotalRecordCount)throw Error('library_changed');total=p.TotalRecordCount;rows.push(...p.Items);}
 if(rows.length!==total||new Set(rows.map(r=>r.Id)).size!==rows.length)throw Error('incomplete_library');return rows;
}
function catalogPath(path){return typeof path==='string'&&path.startsWith('/')&&!path.split('/').some(p=>p==='..'||p==='.')&&!/[\x00-\x1f]/.test(path)?path.replace(/^\/data(?=\/)/,'').replace(/\/$/,''):null;}
function catalogPoster(media){return (media?.images||[]).map(i=>i.coverType==='poster'&&(i.remoteUrl||i.url)).find(u=>typeof u==='string'&&/^https:\/\/(image\.tmdb\.org|artworks\.thetvdb\.com)\/[A-Za-z0-9_./%~-]+$/.test(u))||null;}
function catalogInventory({state,moviePages,seriesPages,movies,series,health,now}){
 try{
  if(health?.storage?.guard!==true||!Number.isFinite(health.checkedAt)||Math.abs(now-health.checkedAt)>120000)throw Error('storage_health_unavailable');
  if(!Array.isArray(movies)||!Array.isArray(series)||[...movies,...series].some(m=>!Number.isSafeInteger(m.id)))throw Error('arr_unavailable');
  const entries={},unresolved=[];
  for(const item of [...catalogPages(moviePages),...catalogPages(seriesPages)]){
   if(!['Movie','Series'].includes(item.Type))continue;
   if(item.IsVirtualItem===true)continue;
   const kind=item.Type==='Movie'?'movie':'tv',path=catalogPath(item.Path),arr=kind==='movie'?movies:series;
   if(!path||typeof item.Id!=='string'||!item.Id||typeof item.Name!=='string'){unresolved.push({title:String(item.Name||'Unknown title'),reason:'missing_path_or_identity'});continue;}
   const ids=Object.fromEntries(Object.entries(item.ProviderIds||{}).map(([k,v])=>[k.toLowerCase(),String(v)]));
   const matches=arr.filter(m=>{const root=catalogPath(m.path);return root&&(kind==='movie'?path.startsWith(root+'/'):path===root);});
   const candidates=[...new Set(matches.map(m=>String(kind==='movie'?m.tmdbId:m.tvdbId)).filter(catalogId))];
   let external=ids[kind==='movie'?'tmdb':'tvdb'];
   if(!catalogId(external)&&candidates.length===1)external=candidates[0];
   if(!catalogId(external)||candidates.length>1||candidates.length===1&&candidates[0]!==external){unresolved.push({title:item.Name,reason:'ambiguous_or_missing_provider_id'});continue;}
   const mediaKey=kind+':'+external,metadata=arr.find(m=>String(kind==='movie'?m.tmdbId:m.tvdbId)===external);
   if(entries[mediaKey]){entries[mediaKey].jellyfinIds.push(item.Id);continue;}
   entries[mediaKey]={mediaKey,mediaType:kind,title:item.Name.slice(0,250),year:Number.isInteger(item.ProductionYear)?item.ProductionYear:null,jellyfinId:item.Id,jellyfinIds:[item.Id],path,posterUrl:catalogPoster(metadata)||state.entries?.[mediaKey]?.posterUrl||null};
  }
  const keys=[...new Set([...Object.keys(entries),...Object.keys(state.entries||{})])].sort(),start=keys.length?(Number.isInteger(state.cursor)?state.cursor:0)%keys.length:0;
  const checkedKeys=Array.from({length:Math.min(50,keys.length)},(_,i)=>keys[(start+i)%keys.length]);
   const targets=checkedKeys.flatMap(key=>entries[key]?.mediaType==='tv'?entries[key].jellyfinIds.map(id=>({mediaKey:key,jellyfinId:id,path:entries[key].path})):[]);
  return {complete:true,identityComplete:!unresolved.length,entries,unresolved,checkedKeys,targets,nextCursor:keys.length?(start+checkedKeys.length)%keys.length:0};
 }catch(e){return {complete:false,error:['storage_health_unavailable','arr_unavailable','library_unavailable','library_changed','incomplete_library'].includes(e.message)?e.message:'invalid_snapshot'};}
}
function catalogFingerprint(entry){return JSON.stringify([entry.mediaKey,entry.title,entry.posterUrl||null,entry.availability?.state,entry.availability?.lastKnown||null]);}
function finishCatalog({plan,inventory,proofs=[],now}){
 const state=JSON.parse(plan.old.contextJson),entries=state.entries,body=plan.body;
 const reply={version:1,ok:true,jobs:[]};
 if(body.action==='ack'){
  const entry=entries[body.mediaKey],lease=entry?.lease;
  if(!lease||lease.id!==body.leaseId||lease.until<=now)return {row:{...plan.old,claimId:'',expiresAt:'2099-01-01T00:00:00.000Z'},reply:{version:1,ok:false,error:'stale_job'}};
  if(body.ok===true){entry.publishedFingerprint=lease.fingerprint;entry.publishedDestination=plan.destination||entry.lease.destination;entry.deliveredAt=now;delete entry.error;delete entry.retryAfter;}
  else{entry.error=body.error==='missing_post'?'missing_post':'publication_failed';entry.retryAfter=now+(entry.error==='missing_post'?6*3600000:10*60000);}
  delete entry.lease;
 }else if(plan.needsSync){
  state.lastSync=now;state.importCursor=plan.importCursor;state.indexingUntil=plan.indexingUntil||0;state.lastError=inventory?.complete?null:inventory?.error||'library_unavailable';
  if(inventory?.complete){
   state.cursor=inventory.nextCursor;state.unresolved=inventory.unresolved;
   for(const [key,media] of Object.entries(inventory.entries))entries[key]={...entries[key],...media};
   for(const key of inventory.checkedKeys){
    const entry=entries[key];if(!entry)continue;
    let available=null;
    if(inventory.entries[key]){
     if(entry.mediaType==='movie')available=true;
     else{const matches=proofs.filter(p=>p.mediaKey===key);if(matches.some(p=>p.ok&&p.available))available=true;else if(matches.length===entry.jellyfinIds.length&&matches.every(p=>p.ok))available=false;}
    }else if(inventory.identityComplete)available=false;
    if(available===null){if(entry.availability){entry.availability={...entry.availability,state:'delayed',lastKnown:entry.availability.lastKnown||entry.availability.state};}entry.missingChecks=0;delete entry.firstMissingAt;continue;}
    if(available){entry.missingChecks=0;delete entry.firstMissingAt;entry.availability={state:'available',checkedAt:now,mediaType:entry.mediaType};}
    else if(entry.availability||entry.knownPost){
     if(!entry.firstMissingAt){entry.firstMissingAt=now;entry.missingChecks=1;}
     if(now-entry.firstMissingAt>=CATALOG_INTERVAL){entry.missingChecks=2;entry.availability={state:'unavailable',checkedAt:now,mediaType:entry.mediaType};}
    }
   }
  }else for(const entry of Object.values(entries)){
   if(entry.availability){entry.availability={...entry.availability,state:'delayed',lastKnown:entry.availability.lastKnown||entry.availability.state};entry.missingChecks=0;delete entry.firstMissingAt;}
  }
 }
 if(body.action==='poll'){
  for(const entry of Object.values(entries)){
   if(reply.jobs.length>=10)break;
   if(!entry.availability||entry.retryAfter>now||entry.lease?.until>now)continue;
   const fingerprint=catalogFingerprint(entry),destination=plan.destination||'';
   if(entry.publishedFingerprint===fingerprint&&entry.publishedDestination===destination)continue;
   const id=plan.claimId+':'+reply.jobs.length;
   entry.lease={id,until:now+15*60000,fingerprint,destination};
   reply.jobs.push({mediaKey:entry.mediaKey,leaseId:id,fingerprint});
  }
 }
 reply.unresolved=(state.unresolved||[]).slice(0,25);reply.unresolvedCount=(state.unresolved||[]).length;reply.catalogCount=Object.keys(entries).length;
 return {row:{...plan.old,contextJson:JSON.stringify(state),claimId:'',expiresAt:'2099-01-01T00:00:00.000Z'},reply};
}
if(typeof module!=='undefined')module.exports={prepareCatalog,catalogInventory,finishCatalog,catalogFingerprint};
