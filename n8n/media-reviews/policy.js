// Review decisions and storage belong to n8n, independently of media jobs.
function reviewId(x){return typeof x==='string'&&/^[1-9][0-9]{0,19}$/.test(x)&&BigInt(x)<2n**64n;}
function reviewPoster(url){return typeof url==='string'&&url.length<=2048&&/^https:\/\/(image\.tmdb\.org|artworks\.thetvdb\.com)\/[A-Za-z0-9_./%~-]+$/.test(url)?url:null;}
function reviewRequestPoster(r){try{return reviewPoster(JSON.parse(r.contextJson)?.posterUrl);}catch{return null;}}
function reviewArtworkIdentity({body:b,rows,users,owners}){
 if(b?.op!=='artwork'||![b.userId,b.guildId,b.channelId,b.postMessageId].every(reviewId)||
    !users.includes(b.userId)||!owners.includes(b.userId)||!Array.isArray(rows))return null;
 const posts=[];
 for(const row of rows.filter(r=>r.source==='discord'&&r.state==='review')){
  let d;try{d=JSON.parse(row.contextJson);}catch{continue;}
  if(d.kind==='post'&&d.guildId===b.guildId&&d.messageChannelId===b.channelId&&d.messageId===b.postMessageId)posts.push(d);
 }
 if(posts.length!==1||!/^(movie|tv):[1-9][0-9]{0,19}$/.test(posts[0].mediaKey))return null;
 const [mediaType,externalId]=posts[0].mediaKey.split(':');
 return {mediaKey:posts[0].mediaKey,mediaType,externalId};
}
function reviewArtworkTarget(input){
 let identity=reviewArtworkIdentity(input);const requests=input.requests;
 if(!identity&&input.body?.noticeId&&input.body.op==='vote'){
  const result=reviewOperation({...input,body:{...input.body,op:'resolve'}});
  if(result.reply.ok&&!result.reply.posterUrl){
   const [mediaType,externalId]=result.reply.mediaKey.split(':');identity={mediaKey:result.reply.mediaKey,mediaType,externalId};
  }
 }
 if(!identity||!Array.isArray(requests))return null;
 const {mediaType,externalId,mediaKey}=identity;
 const candidates=requests.filter(r=>r.source==='discord'&&r.state==='registered'&&r.mediaType===mediaType&&
  String(r.externalId)===externalId&&reviewId(String(r.mediaId)));
 if(!candidates.length||new Set(candidates.map(r=>String(r.mediaId))).size!==1)return null;
 return {mediaKey,externalId,requests:[{mediaType,mediaId:String(candidates[0].mediaId)}]};
}
function reviewArtworkPoster(target,response){
 const r=target?.requests?.[0],m=response?.body;
 if(!r||response.statusCode!==200||!m||String(m.id)!==r.mediaId||
    String(r.mediaType==='movie'?m.tmdbId:m.tvdbId)!==target.externalId||!Array.isArray(m.images))return null;
 for(const image of m.images){if(image?.coverType==='poster'){const url=reviewPoster(image.remoteUrl)||reviewPoster(image.url);if(url)return url;}}
 return null;
}
function verdict(loved,total){
 if(!Number.isInteger(loved)||!Number.isInteger(total)||total<1||loved<0||loved>total)throw Error('invalid_votes');
 const label=loved===0?'🗑️ Straight to the bargain bin':loved*4<total?'🐍 The snake demands a refund':
  loved*2<total?'🍿 Popcorn carried this one':loved*2===total?'⚖️ The couch is divided':
  loved*4<total*3?'👍 Certified pretty good':loved<total?'🔥 The couch approves':'🏆 All hiss, no miss';
 return {label,text:`${label}\n${loved} loved it · ${total-loved} not for them${total<3?'\nEarly verdict—small couch.':''}`};
}
function reviewRequestSelection({body:b,menus,requests,channels,now=Date.now()}){
 if(!b||!Array.isArray(menus)||!Array.isArray(requests)||!channels.includes(b.channelId))return null;
 const matches=menus.filter(m=>String(m.id)===b.myRequestsId&&m.source==='discord'&&
  m.userId===b.userId&&m.destinationId===b.channelId&&m.state==='preview'&&Date.parse(m.expiresAt)>now);
 if(matches.length!==1)return null;
 let browser;try{browser=JSON.parse(matches[0].contextJson).myRequests;}catch{return null;}
 if(!Number.isInteger(browser?.selected)||browser.selected<0||browser.settings)return null;
 const title=browser.titles?.[browser.selected];
 if(!title||!['movie','tv'].includes(title.mediaType)||!reviewId(String(title.mediaId)))return null;
 const candidates=requests.filter(r=>r.source==='discord'&&r.userId===b.userId&&r.state==='registered'&&
  r.mediaType===title.mediaType&&String(r.mediaId)===String(title.mediaId)&&r.title&&reviewId(String(r.externalId)));
 if(!candidates.length||new Set(candidates.map(r=>String(r.externalId))).size!==1)return null;
 const r=candidates[0],mediaKey=r.mediaType+':'+r.externalId;
 if(b.expectedMediaKey&&b.expectedMediaKey!==mediaKey||b.op==='vote'&&!b.expectedMediaKey)return null;
 return {menu:matches[0],mediaKey,mediaType:r.mediaType,mediaId:String(r.mediaId),title:String(r.title).slice(0,250),
  statusActor:{source:'discord',userId:b.userId,query:'',mediaType:r.mediaType,mediaId:String(r.mediaId)}};
}
function reviewOperation({body:b,rows,notices,requests,users,owners,channels,menus=[],availability=null,posterUrl=null,now=Date.now()}){
 const fail=error=>({row:null,reply:{version:1,ok:false,error}});
 if(!Array.isArray(rows)||!Array.isArray(notices)||!Array.isArray(requests))return fail('invalid_snapshot');
 if(!b||![b.userId,b.guildId,b.channelId].every(reviewId)||!users.includes(b.userId))return fail('denied');
 if(b.op==='restore_snapshot'&&!owners.includes(b.userId))return fail('denied');
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
 if(b.op==='posts'){
  if(!owners.includes(b.userId)||!channels.includes(b.channelId))return fail('denied');
  const cursor=b.cursor??0;if(!Number.isSafeInteger(cursor)||cursor<0||cursor>100000)return fail('invalid_cursor');
  const posts=[...saved.values()].filter(d=>d.kind==='post').sort((a,b)=>a._row.requestKey.localeCompare(b._row.requestKey));
  return {row:null,reply:{version:1,ok:true,posts:posts.slice(cursor,cursor+25).map(d=>({channelId:d.channelId,
   messageChannelId:d.messageChannelId,messageId:d.messageId,threadId:d.threadId,mediaKey:d.mediaKey})),nextCursor:cursor+25<posts.length?cursor+25:null}};
 }
 let media,post,menuOriginal,destination=config?.channelId;
 if(b.postMessageId){
  if(b.op==='artwork'&&!owners.includes(b.userId))return fail('denied');
  post=[...saved.values()].find(d=>d.kind==='post'&&d.messageId===b.postMessageId&&d.messageChannelId===b.channelId);
  if(!post)return fail('unknown_post');
  media=post;destination=post.channelId;
 }else if(b.myRequestsId){
  media=reviewRequestSelection({body:b,menus,requests,channels,now});
  if(!media)return fail('invalid_menu');
  if(!Number.isSafeInteger(availability?.available)||availability.available<1)return fail('unavailable');
  media.posterUrl=reviewPoster(posterUrl)||reviewRequestPoster(requests.find(r=>r.source==='discord'&&r.userId===b.userId&&r.mediaType===media.mediaType&&String(r.mediaId)===media.mediaId));
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
  media.posterUrl=reviewPoster(posterUrl)||reviewPoster(payload.posterUrl)||reviewRequestPoster(r);
 }else if(['bind','comment','summary','forget_comment'].includes(b.op)){
  media=[...saved.values()].find(d=>d.kind==='vote'&&d.mediaKey===b.mediaKey&&(owners.includes(b.userId)||d.userId===b.userId));
  if(!media||!owners.includes(b.userId)&&media.userId!==b.userId)return fail('missing_identity');
 }else return fail('invalid_operation');
 if(!destination)return fail('unconfigured');
 const mk=media.mediaKey,pk=key('post',destination+':'+mk);
 post=post||saved.get(pk);
 media={...media,posterUrl:reviewPoster(media.posterUrl)||reviewPoster(post?.posterUrl)||
  [...saved.values()].filter(d=>d.kind==='vote'&&d.mediaKey===mk).map(d=>reviewPoster(d.posterUrl)).find(Boolean)||null};
 let row=null,deleteComment,postOriginal;
 if(b.op==='artwork'){
  if(!post||!owners.includes(b.userId)||!b.postMessageId)return fail('denied');
  const url=reviewPoster(posterUrl)||media.posterUrl;
  if(url&&url!==post.posterUrl){const {_row,...fields}=post;post={...fields,posterUrl:url};row=record(pk,post);}
  media.posterUrl=url;
 }else if(b.op==='open'&&b.myRequestsId){
  menuOriginal=media.menu;row={...menuOriginal,expiresAt:new Date(now+300000).toISOString()};
 }else if(b.op==='vote'){
  if(!['loved','not_for_me'].includes(b.vote))return fail('invalid_vote');
  const vk=key('vote',mk+':'+b.userId),old=saved.get(vk);
  if(b.eventId&&old?.eventId===b.eventId&&old.vote!==b.vote)return fail('invalid_event');
  const d={kind:'vote',mediaKey:mk,title:media.title,posterUrl:media.posterUrl,userId:b.userId,
   vote:b.vote,username:String(b.username||b.userId).slice(0,80),eventId:String(b.eventId||'').slice(0,100)};
  row=record(vk,d);saved.set(vk,d);
 }else if(b.op==='bind'){
  if(![b.threadId,b.messageId,b.messageChannelId].every(reviewId))return fail('invalid_post');
  if(post&&(post.messageId!==b.messageId||post.threadId!==b.threadId)&&
    !(owners.includes(b.userId)&&b.expectedPostMessageId===post.messageId&&b.expectedPostThreadId===post.threadId&&b.expectedMediaKey===mk))return fail('post_conflict');
  if(post)postOriginal=post._row;
  post={kind:'post',mediaKey:mk,title:media.title,posterUrl:media.posterUrl,channelId:destination,
   threadId:b.threadId,messageId:b.messageId,messageChannelId:b.messageChannelId};row=record(pk,post);
 }else if(b.op==='comment'){
  if(!post||!reviewId(b.commentId))return fail('invalid_post');
  row=record(key('comment',destination+':'+mk+':'+b.userId),{kind:'comment',mediaKey:mk,userId:b.userId,channelId:destination,messageId:b.commentId});
 }else if(b.op==='forget_comment'){
  if(!post||!reviewId(b.expectedCommentId))return fail('invalid_comment_reference');
  const ck=key('comment',destination+':'+mk+':'+b.userId),comment=saved.get(ck);
  if(comment){
   if(comment.messageId!==b.expectedCommentId)return fail('comment_reference_changed');
   if(!Number.isSafeInteger(comment._row.id)||comment._row.id<1)return fail('invalid_comment_reference');
   deleteComment={id:comment._row.id,requestKey:comment._row.requestKey,contextJson:comment._row.contextJson};saved.delete(ck);
  }
 }else if(!['resolve','lookup','summary','restore_snapshot'].includes(b.op))return fail('invalid_operation');
 const votes=[...saved.values()].filter(d=>d.kind==='vote'&&d.mediaKey===mk),total=votes.length,loved=votes.filter(d=>d.vote==='loved').length;
 const mine=votes.find(d=>d.userId===b.userId),comment=saved.get(key('comment',destination+':'+mk+':'+b.userId));
 const summary=total?verdict(loved,total):{text:'Be the first on the couch to review this title.'};
 return {row,menuOriginal,deleteComment,postOriginal,reply:{version:1,ok:true,mediaKey:mk,title:media.title,posterUrl:media.posterUrl,
  channelId:destination,post:post?{threadId:post.threadId,messageId:post.messageId,messageChannelId:post.messageChannelId}:null,
  total,loved,summary:summary.text,vote:mine?.vote,username:mine?.username,commentId:comment?.messageId||null,
  ...(b.op==='restore_snapshot'?{votes:votes.map(v=>({userId:v.userId,vote:v.vote,username:v.username}))}:{})}};
}
if(typeof module!=='undefined')module.exports={verdict,reviewOperation,reviewRequestSelection,reviewArtworkIdentity,reviewArtworkTarget,reviewArtworkPoster};
