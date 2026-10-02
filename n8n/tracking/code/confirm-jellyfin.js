const c=$('Candidate Input').first().json;
const data=$input.first().json;
if(!Array.isArray(data.Items) || !data.Items.some(x=>x.Path===c.jellyfinPath && x.Id))return [];
const r=c.request;
const suffix=c.mediaType==='tv'&&c.downloadCount>1 ? (c.remainingCount>0 ? '\nThe remaining episodes you requested will be available soon.' : '\nAll requested episodes are available in Jellyfin.') : '';
const key=c.mediaType==='tv'?'tv-ready':c.fileKey;
return [{json:{notificationKey:`${r.requestKey}:${key}`,requestKey:r.requestKey,fileKey:c.fileKey,source:r.source,destinationId:r.destinationId,payloadJson:JSON.stringify({text:`✅ ${c.label}\n\nDownload complete and available in Jellyfin.${suffix}`,userId:r.userId,messageId:r.messageId}),state:'pending',attempts:0,nextAttemptAt:new Date().toISOString(),deliveredAt:null,deliveredMessageId:''}}];
