// Pure policy functions embedded into native n8n Code nodes.
const DAY_MS=86400000;
function parseRetention(text,type) {
 if(typeof text!=='string'||!['movie','tv'].includes(type))throw new Error('Invalid retention input');
 const permanent=/\b(?:keep\s+(?:permanently|forever)|never\s+delete|do\s+not\s+delete|don't\s+delete|no\s+expiry)\b/gi;
 const timed=/\b(?:keep\s+(?:for\s+)?|retain\s+(?:for\s+)?|delete\s+after\s+|remove\s+after\s+|expire\s+(?:after|in)\s+)([0-9]+)\s+days?\b/gi;
 const forever=[...text.matchAll(permanent)], durations=[...text.matchAll(timed)];
 if(forever.length+durations.length>1)throw new Error('Use one retention instruction');
 let remainder=text.replace(permanent,'').replace(timed,'');
 if(/\b(?:keep\s+for|retain|delete|remove\s+after|expir\w*|keep\s+(?:permanently|forever|[-\d]))\b/i.test(remainder))throw new Error('Use keep for N days or keep permanently');
 const days=forever.length?null:durations.length?Number(durations[0][1]):type==='movie'?7:30;
 if(days!==null&&(!Number.isInteger(days)||days<1||days>3650))throw new Error('Retention must be 1 to 3650 days');
 return {version:2,days,explicit:!!(forever.length||durations.length)};
}
function retentionText(policy,type) {
 if(policy.days===null)return '🗃️ Keep permanently. No automatic deletion.';
 return `🗓️ Auto-delete ${policy.days} days after ${type==='tv'?'each episode imports':'import'}. Watching may shorten this to 7 days after watching; it never extends the deadline.`;
}
function effectiveExpiry(importedAt,days,watchedAt,previousDeadline,minimumExpiry) {
 if(days===null)return null;
 const imported=Date.parse(importedAt);
 if(!Number.isFinite(imported)||!Number.isInteger(days)||days<1||days>3650)throw new Error('Invalid expiry inputs');
 let deadline=imported+days*DAY_MS;
 if(watchedAt!==null&&watchedAt!==undefined){
  const watched=Date.parse(watchedAt);if(!Number.isFinite(watched))throw new Error('Invalid watch timestamp');
  deadline=Math.min(deadline,Math.max(imported,watched)+7*DAY_MS);
 }
 if(previousDeadline){const previous=Date.parse(previousDeadline);if(!Number.isFinite(previous))throw new Error('Invalid saved deadline');deadline=Math.min(deadline,previous);}
 if(minimumExpiry){const floor=Date.parse(minimumExpiry);if(!Number.isFinite(floor))throw new Error('Invalid explicit extension');deadline=Math.max(deadline,floor);}
 return new Date(deadline).toISOString();
}
function subscription(episodes,choice,now) {
 const regular=episodes.filter(e=>Number.isSafeInteger(e.id)&&e.id>0&&Number.isInteger(e.seasonNumber)&&e.seasonNumber>0);
 const historicalSeasons=[...new Set(regular.filter(e=>Number.isFinite(Date.parse(e.airDateUtc))&&Date.parse(e.airDateUtc)<=now).map(e=>e.seasonNumber))].sort((a,b)=>a-b);
 let selectedSeasons;
 if(choice==='all')selectedSeasons=[...new Set(regular.map(e=>e.seasonNumber))];
 else if(choice==='latest')selectedSeasons=[historicalSeasons.at(-1)||Math.min(...regular.map(e=>e.seasonNumber))];
 else if(/^season_[1-9][0-9]{0,3}$/.test(choice))selectedSeasons=[Number(choice.slice(7))];
 else if(/^seasons_[1-9][0-9]{0,3}(?:_[1-9][0-9]{0,3})*$/.test(choice)){selectedSeasons=choice.slice(8).split('_').map(Number);if(selectedSeasons.some((s,i)=>(i&&s<=selectedSeasons[i-1])||!regular.some(e=>e.seasonNumber===s)))throw new Error('Invalid subscription seasons');}
 else throw new Error('Invalid subscription choice');
 if(!selectedSeasons.length||selectedSeasons.some(s=>!Number.isFinite(s)))throw new Error('No season metadata yet');
 const result={historicalSeasons,selectedSeasons,episodeIds:[]};
 result.episodeIds=regular.filter(e=>belongsToSubscription(e,result)).map(e=>String(e.id));
 return result;
}
function belongsToSubscription(e,s) {
 return Number.isSafeInteger(e.id)&&e.id>0&&Number.isInteger(e.seasonNumber)&&e.seasonNumber>0&&
  (s.selectedSeasons.includes(e.seasonNumber)||!s.historicalSeasons.includes(e.seasonNumber));
}
function fileDecision(claims,coveredIds,now) {
 if(!claims.length)return {due:false,reason:'unclaimed',expiresAt:null};
 const covered=new Set(claims.flatMap(c=>c.episodeIds||[]));
 if(coveredIds.some(id=>!covered.has(String(id))))return {due:false,reason:'unclaimed episode in shared file',expiresAt:null};
 let latest=0;
 for(const c of claims){
  if(!c.baselineCaptured||c.preexisting||c.days===null)return {due:false,reason:'protected claim',expiresAt:null};
  const expiry=effectiveExpiry(c.importedAt,c.days,c.watchedAt,c.previousDeadline,c.minimumExpiry);
  latest=Math.max(latest,Date.parse(expiry));
 }
 return {due:latest<=now,reason:latest<=now?'expired':'retained',expiresAt:new Date(latest).toISOString()};
}
function mediaSnapshot(response) {
 if(response.statusCode===404)return null;
 if(response.statusCode!==200||!Number.isSafeInteger(response.body?.id)||response.body.id<1)throw new Error('Media snapshot unavailable');
 return response.body;
}
if(typeof module!=='undefined')module.exports={parseRetention,retentionText,effectiveExpiry,subscription,belongsToSubscription,fileDecision,mediaSnapshot};
