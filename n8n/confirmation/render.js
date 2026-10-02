const r=$json;
if(r.version)return [{json:r}];
const notice=text=>[{json:{version:1,status:'notice',text}}];
if(!r.id)return notice('Unable to prepare that request. Please try again.');
if(r.state==='cancelled')return notice('Request cancelled. Nothing was downloaded.');
if(!['preview','scope','seasons'].includes(r.state))return notice('This request was already handled. Send a new request if needed.');
if(Date.parse(r.expiresAt)<=Date.now())return notice('This request expired. Please send it again.');
const m=JSON.parse(r.mediaJson);
const header=(r.mediaType==='movie'?'🎬 ':'📺 ')+m.title+(m.year?' ('+m.year+')':'');
let choices=[],text=header;
if(r.state==='preview'){
 text+='\n\n'+String(m.overview||'No description available.').slice(0,450)+'\n\nIs this the correct '+(r.mediaType==='movie'?'movie':'series')+'?';
 choices=[{label:'Confirm',action:'confirm'},{label:'Cancel',action:'cancel'}];
}else if(r.state==='scope'){
 text+='\n\nWhich episodes would you like?\nLatest means the newest season with aired episodes. Specials and future episodes are excluded.';
 choices=[{label:'Latest season',action:'latest'},{label:'Choose a season',action:'choose'},{label:'All seasons',action:'all'},{label:'Cancel',action:'cancel'}];
}else{
 const seasons=[...new Set((m.seasons||[]).map(s=>s.seasonNumber).filter(s=>Number.isInteger(s)&&s>0&&s<=9999))].sort((a,b)=>a-b);
 const page=/^page_[0-9]+$/.test(r.choice||'')?Number(r.choice.slice(5)):0;
 text+='\n\nChoose a season. Only aired episodes will be requested.';
 choices=seasons.slice(page*20,page*20+20).map(s=>({label:'Season '+s,action:'season_'+s}));
 if(page>0)choices.push({label:'Previous',action:'page_'+(page-1)});
 if((page+1)*20<seasons.length)choices.push({label:'Next',action:'page_'+(page+1)});
 choices.push({label:'Cancel',action:'cancel'});
}
const poster=(m.images||[]).find(x=>x.coverType==='poster');
const url=poster?.remoteUrl||poster?.url;
const out={version:1,status:'confirmation',text,pendingId:String(r.id),choices};
if(typeof url==='string'&&url.length<=2048&&/^https:\/\/(image\.tmdb\.org|artworks\.thetvdb\.com)\/[A-Za-z0-9_./%~-]+$/.test(url))out.posterUrl=url;
return [{json:out}];
