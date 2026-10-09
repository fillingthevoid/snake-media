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
 const matches=JSON.parse(row.contextJson||'{}').titleMatches;
 if(matches?.active){
  if(actor.action==='back')return row.mediaType==='tv'?'scope':'preview';
  const pick=actor.action.match(/^match_([0-7])$/);
  if(pick&&matches.items?.[Number(pick[1])])return row.mediaType==='tv'?'scope':'preview';
  throw Error('Choose a title first');
 }
 if(['preview','scope','ready'].includes(row.state)&&actor.action==='wrong')return row.mediaType==='tv'?'scope':'preview';
 if(row.state==='seasons'&&actor.action==='back')return 'scope';
 if(row.state==='ready'&&actor.action==='back')return 'seasons';
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
function revise(row,actor,state){
 const ctx=JSON.parse(row.contextJson||'{}'),next={...row,state};
 if(actor.action==='wrong')ctx.titleMatches={...(ctx.titleMatches||{items:[JSON.parse(row.mediaJson)]}),active:true};
 else if(ctx.titleMatches?.active){
  if(/^match_[0-7]$/.test(actor.action)){
   const m=ctx.titleMatches.items[Number(actor.action.slice(6))],field=row.mediaType==='movie'?'tmdbId':'tvdbId';
   if(!Number.isSafeInteger(m?.[field])||m[field]<=0)throw Error('Invalid title identity');
   next.mediaJson=JSON.stringify(m);
  }
  ctx.titleMatches.active=false;
 }
 next.contextJson=JSON.stringify(ctx);return next;
}
function selectedChoice(row,actor,state){
 if(['wrong','back'].includes(actor.action)||/^match_/.test(actor.action))return '';
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
 if(ctx.titleMatches?.active){
  text='Choose the correct '+(row.mediaType==='movie'?'movie':'series')+'.\nIf none match, use /request with a more specific title or year.';
  choices=(ctx.titleMatches.items||[]).slice(0,8).map((m,i)=>({label:(m.title+(m.year?' ('+m.year+')':'')).slice(0,80),action:'match_'+i}));
  choices.push({label:'Back',action:'back'},{label:'Cancel',action:'cancel'});
 }else if(row.state==='preview'){
  text+='\n\n'+String(m.overview||'').slice(0,160)+'\nIs this the correct '+(row.mediaType==='tv'?'series':'movie')+'?';
  choices=[{label:'Confirm',action:'confirm'},{label:'Wrong title?',action:'wrong'},{label:'Cancel',action:'cancel'}];
 }else if(row.state==='scope'){
  text+='\n\n'+String(m.overview||'').slice(0,160)+'\nChoose episodes to download, then confirm. Latest means the newest season with aired episodes. Specials are excluded.';
  choices=[{label:'Latest season',action:'latest'},{label:'All seasons',action:'all'},{label:'Choose a season',action:'choose'},{label:'Wrong title?',action:'wrong'},{label:'Cancel',action:'cancel'}];
 }else if(row.state==='ready'){
  if(!validChoice(row,row.choice))return notice('Choose a season before confirming. Please send a new request.');
  const label=row.choice==='latest'?'Latest season with aired episodes':row.choice==='all'?'All seasons':'Season '+row.choice.slice(7);
  text+='\n\nSelected: '+label+'\nConfirm this title and selection?';
  choices=[{label:'Confirm',action:'confirm'},{label:'Back',action:'back'},{label:'Wrong title?',action:'wrong'},{label:'Cancel',action:'cancel'}];
 }else{
  const seasons=[...new Set((m.seasons||[]).map(s=>s.seasonNumber).filter(s=>Number.isInteger(s)&&s>0&&s<=9999))].sort((a,b)=>a-b);
  const page=/^page_[0-9]+$/.test(row.choice||'')?Number(row.choice.slice(5)):0;
  text+='\n\nChoose a season. You will review it before confirming.';
  choices=seasons.slice(page*20,page*20+20).map(s=>({label:'Season '+s,action:'season_'+s}));
  if(page>0)choices.push({label:'Previous',action:'page_'+(page-1)});
  if((page+1)*20<seasons.length)choices.push({label:'Next',action:'page_'+(page+1)});
  choices.push({label:'Back',action:'back'},{label:'Cancel',action:'cancel'});
 }
 const out={version:1,status:'confirmation',text,pendingId:String(row.id),choices};
 if(ctx.titleMatches?.active)out.menuChoices=[{label:'Correct the search',action:'request'}];
 const poster=(m.images||[]).find(x=>x.coverType==='poster'),url=poster?.remoteUrl||poster?.url;
 if(typeof url==='string'&&url.length<=2048&&/^https:\/\/(image\.tmdb\.org|artworks\.thetvdb\.com)\/[A-Za-z0-9_./%~-]+$/.test(url))out.posterUrl=url;
 return out;
}
if(typeof module!=='undefined')module.exports={transition,selectedChoice,card,revise};
