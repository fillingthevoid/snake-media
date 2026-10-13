const {test}=require('node:test'),assert=require('node:assert/strict');
const r=require('../n8n/media-reviews/policy.js');
const now=Date.parse('2026-10-13T12:00:00Z'),poster='https://image.tmdb.org/t/p/w500/a.jpg';
const config={source:'discord',state:'review',requestKey:'review:config:20',contextJson:JSON.stringify({kind:'config',guildId:'20',channelId:'40'})};
const post={source:'discord',state:'review',requestKey:'review:post:20:40:movie:90',contextJson:JSON.stringify({kind:'post',guildId:'20',channelId:'40',messageChannelId:'60',messageId:'70',threadId:'60',mediaKey:'movie:90',title:'A'})};
const request={source:'discord',userId:'10',state:'registered',requestKey:'r',mediaType:'movie',mediaId:'100',externalId:'90',title:'A'};
const menu={id:7,source:'discord',userId:'10',destinationId:'30',state:'preview',expiresAt:new Date(now+300000).toISOString(),contextJson:JSON.stringify({myRequests:{selected:0,titles:[{mediaType:'movie',mediaId:'100',title:'A'}]}})};
const base={rows:[config],notices:[],requests:[request],menus:[menu],availability:{available:1},users:['10','11'],owners:['10'],channels:['30'],now};
const body={userId:'10',channelId:'30',guildId:'20',myRequestsId:'7',expectedMediaKey:'movie:90',op:'vote',vote:'loved'};

test('status artwork reaches the saved review and survives summary and later votes',()=>{
 const vote=r.reviewOperation({...base,body,posterUrl:poster});
 assert.equal(vote.reply.posterUrl,poster);assert.equal(JSON.parse(vote.row.contextJson).posterUrl,poster);
 const bound=r.reviewOperation({...base,rows:[config,vote.row],body:{userId:'10',channelId:'30',guildId:'20',op:'bind',mediaKey:'movie:90',messageChannelId:'60',messageId:'70',threadId:'60'}});
 const next=r.reviewOperation({...base,rows:[config,vote.row,bound.row],body:{userId:'11',channelId:'60',guildId:'20',postMessageId:'70',op:'vote',vote:'not_for_me'}});
 assert.equal(next.reply.posterUrl,poster);assert.equal(next.reply.total,2);
 const summary=r.reviewOperation({...base,rows:[config,vote.row,bound.row,next.row],body:{userId:'11',channelId:'60',guildId:'20',op:'summary',mediaKey:'movie:90'}});
 assert.equal(summary.reply.posterUrl,poster);
});
test('artwork maintenance requires owner and registered post plus unambiguous saved media identity',()=>{
 const b={userId:'10',channelId:'60',guildId:'20',postMessageId:'70',op:'artwork'};
 const input={...base,rows:[config,post],body:b};
 const target=r.reviewArtworkTarget(input);assert.equal(target.mediaKey,'movie:90');assert.equal(target.requests[0].mediaId,'100');
 for(const extra of [{body:{...b,userId:'11'}},{body:{...b,channelId:'61'}},{body:{...b,postMessageId:'71'}},{requests:[{...request,source:'telegram'}]},{requests:[request,{...request,mediaId:'101'}]}])assert.equal(r.reviewArtworkTarget({...input,...extra}),null);
 assert.equal(r.reviewArtworkPoster(target,{statusCode:200,body:{id:100,tmdbId:90,images:[{coverType:'poster',remoteUrl:poster}]}}),poster);
 for(const response of [{statusCode:404},{statusCode:200,body:{id:101,tmdbId:90}},{statusCode:200,body:{id:100,tmdbId:91}},{error:'timeout'}])assert.equal(r.reviewArtworkPoster(target,response),null);
 const written=r.reviewOperation({...input,posterUrl:poster});assert.equal(JSON.parse(written.row.contextJson).posterUrl,poster);assert.equal(written.reply.total,0);
 assert.equal(r.reviewOperation({...input,body:{...b,userId:'11'},posterUrl:poster}).reply.error,'denied');
});
test('unsafe and missing artwork cannot erase saved poster or accept a credential URL',()=>{
 const saved={...post,contextJson:JSON.stringify({...JSON.parse(post.contextJson),posterUrl:poster})};
 const b={userId:'10',channelId:'60',guildId:'20',postMessageId:'70',op:'artwork'};
 for(const url of [null,'http://192.168.0.200/image.jpg','https://image.tmdb.org/a.jpg?token=secret','https://user:password@image.tmdb.org/a.jpg','https://example.com/a.jpg']){
  const out=r.reviewOperation({...base,rows:[config,saved],body:b,posterUrl:url});assert.equal(out.reply.posterUrl,poster);assert.equal(out.row,null);
 }
 const tv={...r.reviewArtworkTarget({...base,rows:[config,post],body:b}),mediaKey:'tv:90',requests:[{mediaType:'tv',mediaId:'100'}]};
 assert.equal(r.reviewArtworkPoster(tv,{statusCode:200,body:{id:100,tvdbId:90,images:[{coverType:'poster',remoteUrl:'https://artworks.thetvdb.com/poster.jpg'}]}}),'https://artworks.thetvdb.com/poster.jpg');
});
test('first expiry-reminder vote gets exact artwork without repeating metadata reads after it is saved',()=>{
 const notice={id:8,source:'discord',destinationId:'30',requestKey:'r',deliveredAt:new Date(now-1000).toISOString(),payloadJson:JSON.stringify({kind:'expiry_reminder'})};
 const b={userId:'11',channelId:'30',guildId:'20',noticeId:'8',op:'vote',vote:'loved'};
 const input={...base,body:b,notices:[notice]};
 assert.equal(r.reviewArtworkTarget(input)?.mediaKey,'movie:90');
 const result=r.reviewOperation({...input,posterUrl:poster});assert.equal(result.reply.posterUrl,poster);
 assert.equal(r.reviewArtworkTarget({...input,rows:[config,result.row]}),null);
 assert.equal(r.reviewArtworkTarget({...input,now:now+21600001}),null);
 assert.equal(r.reviewArtworkTarget({...input,body:{...b,userId:'99'}}),null);
});
