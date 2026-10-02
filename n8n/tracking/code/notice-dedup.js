const c=$('Candidate Input').first().json;
const key=c.request.requestKey+':'+(c.mediaType==='tv'?'tv-ready':c.fileKey);
const exists=$input.all().some(({json:r})=>r.notificationKey===key ||
 (c.mediaType==='tv'&&r.requestKey===c.request.requestKey&&r.state==='delivered'));
return exists?[]:[{json:c}];
