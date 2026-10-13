// Review decisions and storage belong to n8n, independently of media jobs.
function reviewId(x){return typeof x==='string'&&/^[1-9][0-9]{0,19}$/.test(x)&&BigInt(x)<2n**64n;}
function verdict(loved,total){
 if(!Number.isInteger(loved)||!Number.isInteger(total)||total<1||loved<0||loved>total)throw Error('invalid_votes');
 const label=loved===0?'🗑️ Straight to the bargain bin':loved*4<total?'🐍 The snake demands a refund':
  loved*2<total?'🍿 Popcorn carried this one':loved*2===total?'⚖️ The couch is divided':
  loved*4<total*3?'👍 Certified pretty good':loved<total?'🔥 The couch approves':'🏆 All hiss, no miss';
 return {label,text:`${label}\n${loved} loved it · ${total-loved} not for them${total<3?'\nEarly verdict—small couch.':''}`};
}
function reviewOperation({body:b,rows,notices,requests,users,owners,channels,now=Date.now()}){
 const fail=error=>({row:null,reply:{version:1,ok:false,error}});
 if(!Array.isArray(rows)||!Array.isArray(notices)||!Array.isArray(requests))return fail('invalid_snapshot');
 if(!b||![b.userId,b.guildId,b.channelId].every(reviewId)||!users.includes(b.userId))return fail('denied');
 const saved=new Map();
 for(const r of rows.filter(r=>r.source==='discord'&&r.state==='review')){
  let d;try{d=JSON.parse(r.contextJson);}catch{return fail('invalid_snapshot');}
  if(d.guildId===b.guildId)saved.set(r.requestKey,{...d,_row:r});
 }
 const key=(kind,suffix='')=>`review:${kind}:${b.guildId}${suffix?':'+suffix:''}`;
 const record=(requestKey,d)=>({source:'discord',userId:b.userId,destinationId:b.channelId,messageId:'0',
  requestedAt:new Date(now).toISOString(),requestKey,state:'review',expiresAt:'2099-01-01T00:00:00.000Z',contextJson:JSON.stringify({...d,guildId:b.guildId})});
 let config=saved.get(key('config'));
 if(b.op==='setup'){
  if(!owners.includes(b.userId)||!channels.includes(b.channelId)||!reviewId(b.targetChannelId))return fail('denied');
  return {row:record(key('config'),{kind:'config',channelId:b.targetChannelId}),reply:{version:1,ok:true,channelId:b.targetChannelId}};
 }
 if(b.op==='config')return {row:null,reply:{version:1,ok:true,channelId:config?.channelId||null}};
 let media,post,destination=config?.channelId;
 if(b.postMessageId){
  post=[...saved.values()].find(d=>d.kind==='post'&&d.messageId===b.postMessageId&&d.messageChannelId===b.channelId);
  if(!post)return fail('unknown_post');
  media=post;destination=post.channelId;
 }else if(b.noticeId){
  const n=notices.find(n=>String(n.id)===b.noticeId);let payload;
  try{payload=JSON.parse(n?.payloadJson);}catch{return fail('invalid_notice');}
  if(n.source!=='discord'||n.destinationId!==b.channelId||payload.kind!=='expiry_reminder'||
   !channels.includes(b.channelId)||!n.deliveredAt||Date.parse(n.deliveredAt)>now||
   now-Date.parse(n.deliveredAt)>21600000||!Number.isFinite(Date.parse(n.deliveredAt))||
   (b.originMessageId&&b.originMessageId!==n.deliveredMessageId))return fail('invalid_notice');
  const r=requests.find(r=>r.requestKey===n.requestKey&&r.source==='discord');
  if(!r||!['movie','tv'].includes(r.mediaType)||!reviewId(String(r.externalId))||!r.title)return fail('missing_identity');
  media={mediaKey:r.mediaType+':'+r.externalId,title:String(r.title).slice(0,250)};
  try{media.posterUrl=JSON.parse(r.contextJson)?.posterUrl;}catch{}
 }else if(['bind','comment','summary'].includes(b.op)){
  media=[...saved.values()].find(d=>d.kind==='vote'&&d.mediaKey===b.mediaKey&&(owners.includes(b.userId)||d.userId===b.userId));
  if(!media||!owners.includes(b.userId)&&media.userId!==b.userId)return fail('missing_identity');
 }else return fail('invalid_operation');
 if(!destination)return fail('unconfigured');
 const mk=media.mediaKey,pk=key('post',destination+':'+mk);
 post=post||saved.get(pk);
 let row=null;
 if(b.op==='vote'){
  if(!['loved','not_for_me'].includes(b.vote))return fail('invalid_vote');
  const vk=key('vote',mk+':'+b.userId),old=saved.get(vk);
  if(b.eventId&&old?.eventId===b.eventId&&old.vote!==b.vote)return fail('invalid_event');
  const d={kind:'vote',mediaKey:mk,title:media.title,posterUrl:media.posterUrl,userId:b.userId,
   vote:b.vote,username:String(b.username||b.userId).slice(0,80),eventId:String(b.eventId||'').slice(0,100)};
  row=record(vk,d);saved.set(vk,d);
 }else if(b.op==='bind'){
  if(![b.threadId,b.messageId,b.messageChannelId].every(reviewId))return fail('invalid_post');
  if(post&&(post.messageId!==b.messageId||post.threadId!==b.threadId))return fail('post_conflict');
  post={kind:'post',mediaKey:mk,title:media.title,posterUrl:media.posterUrl,channelId:destination,
   threadId:b.threadId,messageId:b.messageId,messageChannelId:b.messageChannelId};row=record(pk,post);
 }else if(b.op==='comment'){
  if(!post||!reviewId(b.commentId))return fail('invalid_post');
  row=record(key('comment',destination+':'+mk+':'+b.userId),{kind:'comment',mediaKey:mk,userId:b.userId,channelId:destination,messageId:b.commentId});
 }else if(!['resolve','lookup','summary'].includes(b.op))return fail('invalid_operation');
 const votes=[...saved.values()].filter(d=>d.kind==='vote'&&d.mediaKey===mk),total=votes.length,loved=votes.filter(d=>d.vote==='loved').length;
 const mine=votes.find(d=>d.userId===b.userId),comment=saved.get(key('comment',destination+':'+mk+':'+b.userId));
 const summary=total?verdict(loved,total):{text:'Be the first on the couch to review this title.'};
 return {row,reply:{version:1,ok:true,mediaKey:mk,title:media.title,posterUrl:media.posterUrl,
  channelId:destination,post:post?{threadId:post.threadId,messageId:post.messageId,messageChannelId:post.messageChannelId}:null,
  total,loved,summary:summary.text,vote:mine?.vote,username:mine?.username,commentId:comment?.messageId||null}};
}
if(typeof module!=='undefined')module.exports={verdict,reviewOperation};
