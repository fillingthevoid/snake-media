function normalizeEvent(body,kind,now){
 if(body?.eventType==='Test')return null;
 if(!['movie','tv'].includes(kind)||!Number.isFinite(now)||!['Grab','Download'].includes(body?.eventType))throw new Error('Invalid media event');
 const id=x=>Number.isSafeInteger(x)&&x>0;
 const media=kind==='movie'?body.movie:body.series;
 if(!id(media?.id))throw new Error('Invalid event media ID');
 const downloadId=body.downloadId??'';
 if(typeof downloadId!=='string'||downloadId.length>200||!/^[A-Za-z0-9_.-]*$/.test(downloadId))throw new Error('Invalid download ID');
 const episodes=kind==='tv'?body.episodes:[];
 if(!Array.isArray(episodes)||episodes.length>5000||(kind==='tv'&&!episodes.length)||episodes.some(e=>!id(e?.id)))throw new Error('Invalid event episodes');
 const file=kind==='movie'?body.movieFile:body.episodeFile;
 if(body.eventType==='Download'&&!id(file?.id))throw new Error('Invalid imported file ID');
 if(body.eventType==='Grab'&&!downloadId)throw new Error('Missing download ID');
 const episodeIds=[...new Set(episodes.map(e=>String(e.id)))].sort((a,b)=>Number(a)-Number(b));
 const receivedAt=new Date(now).toISOString(),fileId=body.eventType==='Download'?String(file.id):'';
 return {eventKey:`${kind}:${media.id}:${body.eventType}:${fileId||downloadId}`,mediaType:kind,mediaId:String(media.id),fileId,
  episodeIdsJson:JSON.stringify(episodeIds),state:body.eventType==='Download'?'imported':'downloading',
  payloadJson:JSON.stringify({eventType:body.eventType,downloadId}),
  importedAt:body.eventType==='Download'?receivedAt:null,receivedAt};
}
function affectedRequests(requests,events,now){
 const fallback=new Date(now).getUTCMinutes()%15===0;
 return requests.filter(r=>{
  const requested=Date.parse(r.requestedAt);
  if(!Number.isFinite(requested)||requested>now+60000)return false;
  if(fallback||now-requested<15*60000)return true;
  let scope;try{scope=new Set(JSON.parse(r.episodeIdsJson||'[]').map(String));}catch{return false;}
  return events.some(e=>{
   const received=Date.parse(e.receivedAt);
   if(!Number.isFinite(received)||received<now-30*60000||received>now+60000||received<requested-60000||
       e.mediaType!==r.mediaType||e.mediaId!==r.mediaId||!['downloading','imported'].includes(e.state))return false;
   if(r.mediaType==='movie')return true;
   try{return JSON.parse(e.episodeIdsJson).some(id=>scope.has(String(id)));}catch{return false;}
  });
 });
}
function libraryRows(pages){
 if(!Array.isArray(pages)||pages.some(p=>!Array.isArray(p?.Items)))throw new Error('Jellyfin snapshot unavailable');
 const rows=pages.flatMap(p=>p.Items),total=Math.max(0,...pages.map(p=>Number(p.TotalRecordCount)||0));
 if(rows.length<total)throw new Error('Incomplete Jellyfin snapshot');
 return rows;
}
function libraryPath(path){
 if(typeof path!=='string'||!/^\/(movies|tv)\/[^/]/.test(path)||path.split('/').some(p=>p==='..'||p==='.')||/[\x00-\x1f]/.test(path))throw new Error('Invalid media directory');
 return '/data'+path.replace(/\/$/,'');
}
function targetRoot(kind,path,pages){
 const root=libraryPath(path);
 const matches=libraryRows(pages).filter(x=>x?.Path===root&&typeof x.Id==='string'&&x.Id);
 const ids=[...new Set(matches.map(x=>x.Id))];
 if(ids.length>1)throw new Error('Ambiguous Jellyfin directory');
 return ids[0]||null;
}
function targetFiles(path,pages){
 const root=libraryPath(path)+'/';
 return libraryRows(pages).filter(x=>typeof x?.Id==='string'&&x.Id&&typeof x.Path==='string'&&x.Path.startsWith(root))
  .map(x=>({Id:x.Id,Path:x.Path}));
}
if(typeof module!=='undefined')module.exports={normalizeEvent,affectedRequests,targetRoot,targetFiles};
