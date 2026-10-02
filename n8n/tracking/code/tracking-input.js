const r = $('Normalize Media Metadata').first().json;
const c = r.context;
if (!c) throw new Error('Missing original request context');
let episodeIds = [], preexistingFileIds = [];
if (r.mediaType === 'tv') {
 const episodes = $input.all().map(x=>x.json).filter(x=>Number.isSafeInteger(x.id) && x.id>0);
 if (!episodes.length) throw new Error('No resolved episode scope; registration deferred');
 episodeIds = episodes.map(x=>String(x.id));
 if (r.status === 'already_added') preexistingFileIds = episodes.filter(x=>Number.isSafeInteger(x.episodeFileId) && x.episodeFileId>0).map(x=>String(x.episodeFileId));
} else if (r.status === 'already_added' && r.raw.movieFile?.id) {
 preexistingFileIds = [String(r.raw.movieFile.id)];
}
return [{json:{...c,mediaType:r.mediaType,mediaId:r.mediaId,externalId:r.externalId,title:r.title,episodeIds,preexistingFileIds,baselineCaptured:true,retentionDays:null}}];
