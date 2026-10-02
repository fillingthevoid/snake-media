// Shared pure decisions embedded into n8n Code nodes by build.py.
function scope(episodes,choice,now) {
 const aired=episodes.filter(e=>Number.isSafeInteger(e.id)&&e.id>0&&Number.isInteger(e.seasonNumber)&&e.seasonNumber>0&&Number.isFinite(Date.parse(e.airDateUtc))&&Date.parse(e.airDateUtc)<=now);
 if(choice==='all')return aired;
 let season;
 if(choice==='latest')season=Math.max(0,...aired.map(e=>e.seasonNumber));
 else if(/^season_[1-9][0-9]{0,3}$/.test(choice))season=Number(choice.slice(7));
 else throw new Error('Invalid season choice');
 return aired.filter(e=>e.seasonNumber===season);
}
function transition(row,actor,now) {
 if(!row||!['discord','telegram'].includes(row.source)||['source','userId','destinationId'].some(k=>row[k]!==actor[k]))throw new Error('Not your request');
 if(!Number.isFinite(Date.parse(row.expiresAt))||Date.parse(row.expiresAt)<=now)throw new Error('Request expired');
 if(!['preview','scope','seasons'].includes(row.state))throw new Error('Already handled');
 if(actor.action==='cancel')return 'cancelled';
 if(row.state==='preview'&&actor.action==='confirm')return row.mediaType==='tv'?'scope':'processing';
 if(row.mediaType==='tv'&&row.state==='scope'&&actor.action==='choose')return 'seasons';
 if(row.mediaType==='tv'&&row.state==='seasons'&&/^page_[0-9]{1,3}$/.test(actor.action))return 'seasons';
 if(row.mediaType==='tv'&&row.state==='scope'&&['latest','all'].includes(actor.action))return 'processing';
 if(row.mediaType==='tv'&&row.state==='seasons'&&/^season_[1-9][0-9]{0,3}$/.test(actor.action))return 'processing';
 throw new Error('Stale or invalid choice');
}
if(typeof module!=='undefined')module.exports={scope,transition};
