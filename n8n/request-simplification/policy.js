function validChoice(row,choice){
 if(['latest','all'].includes(choice))return true;
 if(/^seasons_[1-9][0-9]{0,3}(?:_[1-9][0-9]{0,3})*$/.test(choice||'')){
  const numbers=choice.slice(8).split('_').map(Number);
  return numbers.length<=9999&&numbers.every((n,i)=> (!i||n>numbers[i-1])&&validChoice(row,'season_'+n));
 }
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
 if(row.state==='seasons'){
  const ctx=JSON.parse(row.contextJson||'{}'),seasons=[...new Set(JSON.parse(row.mediaJson).seasons.map(s=>s.seasonNumber).filter(n=>Number.isInteger(n)&&n>0&&n<=9999))].sort((a,b)=>a-b);
  if(/^page_[0-9]{1,3}$/.test(actor.action)&&Number(actor.action.slice(5))<Math.ceil(seasons.length/20))return 'seasons';
  if(/^season_/.test(actor.action)&&validChoice(row,actor.action)&&seasons.slice((ctx.seasonPage||0)*20,(ctx.seasonPage||0)*20+20).includes(Number(actor.action.slice(7))))return 'seasons';
  if(actor.action==='review'&&validChoice(row,'seasons_'+(ctx.selectedSeasons||[]).join('_')))return 'ready';
 }
 if(row.state==='scope'&&['latest','all'].includes(actor.action))return 'ready';
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
   next.mediaJson=JSON.stringify(m);delete ctx.selectedSeasons;delete ctx.seasonPage;
  }
  ctx.titleMatches.active=false;
 }
 if(row.mediaType==='tv'&&!ctx.titleMatches?.active){
  if(actor.action==='choose'&&row.state==='scope'){ctx.selectedSeasons=ctx.selectedSeasons||[];ctx.seasonPage=ctx.seasonPage||0;}
  if(row.state==='seasons'&&/^season_/.test(actor.action)){const n=Number(actor.action.slice(7)),selected=new Set(ctx.selectedSeasons||[]);if(selected.has(n))selected.delete(n);else selected.add(n);ctx.selectedSeasons=[...selected].sort((a,b)=>a-b);}
  if(row.state==='seasons'&&/^page_/.test(actor.action))ctx.seasonPage=Number(actor.action.slice(5));
  if(row.state==='ready'&&actor.action==='back'&&/^season_/.test(row.choice||'')){ctx.selectedSeasons=[Number(row.choice.slice(7))];ctx.seasonPage=0;}
 }
 next.contextJson=JSON.stringify(ctx);return next;
}
function selectedChoice(row,actor,state){
 if(actor.action==='review')return 'seasons_'+JSON.parse(row.contextJson||'{}').selectedSeasons.join('_');
 if(state==='seasons')return '';
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
  choices=[{label:'Latest season',action:'latest'},{label:'All seasons',action:'all'},{label:'Choose seasons',action:'choose'},{label:'Wrong title?',action:'wrong'},{label:'Cancel',action:'cancel'}];
 }else if(row.state==='ready'){
  if(!validChoice(row,row.choice))return notice('Choose a season before confirming. Please send a new request.');
  const label=/^seasons_/.test(row.choice)?'Seasons '+row.choice.slice(8).split('_').join(', '):row.choice==='latest'?'Latest season with aired episodes':row.choice==='all'?'All seasons':'Season '+row.choice.slice(7);
  text+='\n\nSelected: '+label+'\nConfirm this title and selection?';
  choices=[{label:'Confirm',action:'confirm'},{label:'Back',action:'back'},{label:'Wrong title?',action:'wrong'},{label:'Cancel',action:'cancel'}];
 }else{
  const seasons=[...new Set((m.seasons||[]).map(s=>s.seasonNumber).filter(s=>Number.isInteger(s)&&s>0&&s<=9999))].sort((a,b)=>a-b);
  const page=ctx.seasonPage||0,selected=ctx.selectedSeasons||[];
  text+='\n\nTap seasons to select or deselect them, then review.\nSelected: '+(selected.length?'Seasons '+selected.join(', '):'None');
  choices=seasons.slice(page*20,page*20+20).map(s=>({label:(selected.includes(s)?'✅ ':'')+'Season '+s,action:'season_'+s}));
  if(page>0)choices.push({label:'Previous',action:'page_'+(page-1)});
  if((page+1)*20<seasons.length)choices.push({label:'Next',action:'page_'+(page+1)});
  if(selected.length)choices.push({label:'Review selection',action:'review'});
  choices.push({label:'Back',action:'back'},{label:'Cancel',action:'cancel'});
 }
 const out={version:1,status:'confirmation',text,pendingId:String(row.id),choices};
 if(ctx.titleMatches?.active)out.menuChoices=[{label:'Correct the search',action:'request'}];
 const poster=(m.images||[]).find(x=>x.coverType==='poster'),url=poster?.remoteUrl||poster?.url;
 if(typeof url==='string'&&url.length<=2048&&/^https:\/\/(image\.tmdb\.org|artworks\.thetvdb\.com)\/[A-Za-z0-9_./%~-]+$/.test(url))out.posterUrl=url;
 return out;
}
if(typeof module!=='undefined')module.exports={transition,selectedChoice,card,revise};
