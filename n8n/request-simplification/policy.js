function validChoice(row,choice){
 if(['latest','all'].includes(choice))return true;
 if(!/^season_[1-9][0-9]{0,3}$/.test(choice||''))return false;
 try{return JSON.parse(row.mediaJson).seasons.some(s=>s.seasonNumber===Number(choice.slice(7)));}catch{return false;}
}
function transition(row,actor,now){
 if(!row||!['discord','telegram'].includes(row.source)||['source','userId','destinationId'].some(k=>row[k]!==actor[k]))throw Error('Not your request');
 if(!Number.isFinite(Date.parse(row.expiresAt))||Date.parse(row.expiresAt)<=now)throw Error('Request expired');
 if(!['preview','scope','seasons','ready'].includes(row.state))throw Error('Already handled');
 if(actor.action==='cancel')return 'cancelled';
 if(row.state==='preview'&&actor.action==='confirm')return row.mediaType==='tv'?'scope':'processing';
 if(row.mediaType!=='tv')throw Error('Invalid choice');
 if(row.state==='scope'&&actor.action==='choose')return 'seasons';
 if(row.state==='seasons'&&/^page_[0-9]{1,3}$/.test(actor.action))return 'seasons';
 if(row.state==='scope'&&['latest','all'].includes(actor.action))return 'ready';
 if(row.state==='seasons'&&/^season_/.test(actor.action)&&validChoice(row,actor.action))return 'ready';
 if(row.state==='ready'&&actor.action==='choose')return 'scope';
 if(row.state==='ready'&&actor.action==='confirm'&&validChoice(row,row.choice))return 'processing';
 throw Error('Stale or invalid choice');
}
function selectedChoice(row,actor,state){
 if(state==='scope')return '';
 return row.mediaType==='tv'&&row.state==='ready'&&state==='processing'?row.choice:actor.action;
}
function card(row){
 if(row.version)return row;
 const notice=text=>({version:1,status:'notice',text});
 if(!row.id)return notice('Unable to prepare that request. Please try again.');
 if(row.state==='cancelled')return notice('Request cancelled. No media was added.');
 if(!['preview','scope','seasons','ready'].includes(row.state))return notice('This request was already handled. Send a new request if needed.');
 if(!Number.isFinite(Date.parse(row.expiresAt))||Date.parse(row.expiresAt)<=Date.now())return notice('This request expired. Please send it again.');
 const m=JSON.parse(row.mediaJson),ctx=JSON.parse(row.contextJson||'{}');
 const days=ctx.retentionPolicy?ctx.retentionPolicy.days:row.mediaType==='tv'?30:7;
 let text=(row.mediaType==='movie'?'🎬 ':'📺 ')+m.title+(m.year?' ('+m.year+')':'');
 text+='\n'+(days===null?'Keep permanently. No automatic deletion.':`Auto-delete: ${days} days after ${row.mediaType==='tv'?'each episode imports':'import'}. Watching may shorten it to 7 days; never extends expiry.`);
 if(row.mediaType==='tv')text+='\nNew episodes in selected seasons and future seasons download automatically.';
 let choices=[];
 if(row.state==='preview'){
  text+='\n\n'+String(m.overview||'').slice(0,160)+'\nIs this the correct '+(row.mediaType==='tv'?'series':'movie')+'?';
  choices=[{label:'Confirm',action:'confirm'},{label:'Cancel',action:'cancel'}];
 }else if(row.state==='scope'){
  text+='\n\n'+String(m.overview||'').slice(0,160)+'\nChoose episodes to download, then confirm. Latest means the newest season with aired episodes. Specials are excluded.';
  choices=[{label:'Latest season',action:'latest'},{label:'All seasons',action:'all'},{label:'Choose a season',action:'choose'},{label:'Cancel',action:'cancel'}];
 }else if(row.state==='ready'){
  if(!validChoice(row,row.choice))return notice('Choose a season before confirming. Please send a new request.');
  const label=row.choice==='latest'?'Latest season with aired episodes':row.choice==='all'?'All seasons':'Season '+row.choice.slice(7);
  text+='\n\nSelected: '+label+'\nConfirm this title and selection?';
  choices=[{label:'Confirm',action:'confirm'},{label:'Change selection',action:'choose'},{label:'Cancel',action:'cancel'}];
 }else{
  const seasons=[...new Set((m.seasons||[]).map(s=>s.seasonNumber).filter(s=>Number.isInteger(s)&&s>0&&s<=9999))].sort((a,b)=>a-b);
  const page=/^page_[0-9]+$/.test(row.choice||'')?Number(row.choice.slice(5)):0;
  text+='\n\nChoose a season. You will review it before confirming.';
  choices=seasons.slice(page*20,page*20+20).map(s=>({label:'Season '+s,action:'season_'+s}));
  if(page>0)choices.push({label:'Previous',action:'page_'+(page-1)});
  if((page+1)*20<seasons.length)choices.push({label:'Next',action:'page_'+(page+1)});
  choices.push({label:'Cancel',action:'cancel'});
 }
 const out={version:1,status:'confirmation',text,pendingId:String(row.id),choices};
 const poster=(m.images||[]).find(x=>x.coverType==='poster'),url=poster?.remoteUrl||poster?.url;
 if(typeof url==='string'&&url.length<=2048&&/^https:\/\/(image\.tmdb\.org|artworks\.thetvdb\.com)\/[A-Za-z0-9_./%~-]+$/.test(url))out.posterUrl=url;
 return out;
}
if(typeof module!=='undefined')module.exports={transition,selectedChoice,card};
