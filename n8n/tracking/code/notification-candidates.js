const r=$('Inspect Request').first().json;
if(!r.baselineCaptured || !r.requestKey || r.userId==='1' || !['discord','telegram'].includes(r.source))return [];
const before=new Set(JSON.parse(r.preexistingFileIdsJson));
const scope=new Set(JSON.parse(r.episodeIdsJson));
const requested=Date.parse(r.requestedAt);
if(!Number.isFinite(requested))return [];
const candidates=[];
let items=$input.all();
let downloadCount=0,remainingCount=0;
if(r.mediaType==='tv') {
 const selected=items.filter(x=>scope.has(String(x.json.id)));
 // An incomplete API response must not move the notification to a later episode.
 if(new Set(selected.map(x=>String(x.json.id))).size!==scope.size)return [];
 const downloads=selected.filter(({json:e})=>!before.has(String(e.episodeFile?.id ?? e.episodeFileId)));
 if(downloads.some(({json:e})=>!Number.isSafeInteger(e.seasonNumber)||!Number.isSafeInteger(e.episodeNumber)))return [];
 downloads.sort((a,b)=>a.json.seasonNumber-b.json.seasonNumber||a.json.episodeNumber-b.json.episodeNumber||a.json.id-b.json.id);
 downloadCount=downloads.length;
 remainingCount=downloads.slice(1).filter(({json:e})=>!e.episodeFile?.path || !(r.jellyfinLibrary||[]).some(x=>x.Id&&x.Path==='/data'+e.episodeFile.path)).length;
 items=downloads.slice(0,1);
}
for(const item of items) {
 const e=item.json;
 const f=r.mediaType==='movie'?e.movieFile:e.episodeFile;
 if(!f || !Number.isSafeInteger(f.id) || f.id<1 || before.has(String(f.id)))continue;
 if(r.mediaType==='tv' && !scope.has(String(e.id)))continue;
 const imported=Date.parse(f.dateAdded);
 if(!Number.isFinite(imported) || imported<requested || imported>Date.now()+60000)continue;
 const prefix=r.mediaType==='movie'?'/movies/':'/tv/';
 if(typeof f.path!=='string' || !f.path.startsWith(prefix) || f.path.includes('/../'))continue;
 const fileKey=r.mediaType==='movie'?`movie:${r.mediaId}`:`tv:${r.mediaId}:episode:${e.id}`;
 const label=r.mediaType==='movie'?r.title:`${r.title} — S${String(e.seasonNumber).padStart(2,'0')}E${String(e.episodeNumber).padStart(2,'0')}`;
 const {jellyfinLibrary,...originalRequest}=r;
 const jellyfinItems=(jellyfinLibrary||[]).filter(x=>x.Path==='/data'+f.path);
 candidates.push({json:{jellyfinItems,request:originalRequest,fileKey,fileId:String(f.id),importedAt:new Date(imported).toISOString(),jellyfinPath:'/data'+f.path,label,downloadCount,remainingCount,providerId:r.mediaType==='movie'?`tmdb.${r.externalId}`:`tvdb.${e.tvdbId}`,mediaType:r.mediaType}});
}
return candidates;
