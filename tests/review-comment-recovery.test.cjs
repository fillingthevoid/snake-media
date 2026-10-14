const {test}=require('node:test'),assert=require('node:assert/strict');
const {reviewOperation}=require('../n8n/media-reviews/policy.js');
const config={source:'discord',state:'review',requestKey:'review:config:20',contextJson:JSON.stringify({kind:'config',guildId:'20',channelId:'40'})};
const vote={source:'discord',state:'review',requestKey:'review:vote:20:tv:90:10',contextJson:JSON.stringify({kind:'vote',guildId:'20',mediaKey:'tv:90',userId:'10',vote:'loved',title:'A'})};
const post={id:4,source:'discord',state:'review',requestKey:'review:post:20:40:tv:90',contextJson:JSON.stringify({kind:'post',guildId:'20',mediaKey:'tv:90',title:'A',channelId:'40',messageChannelId:'60',messageId:'70',threadId:'60'})};
const comment={id:5,source:'discord',state:'review',requestKey:'review:comment:20:40:tv:90:10',contextJson:JSON.stringify({kind:'comment',guildId:'20',mediaKey:'tv:90',channelId:'40',userId:'10',messageId:'80'})};
const base={rows:[config,vote,post,comment],requests:[],notices:[],users:['10','11'],owners:['10'],channels:['30']};
const body={userId:'10',guildId:'20',channelId:'60',postMessageId:'70',mediaKey:'tv:90'};
test('confirmed deleted comment plans an exact reference deletion without changing votes',()=>{
 const out=reviewOperation({...base,body:{...body,op:'forget_comment',expectedCommentId:'80'}});
 assert.equal(out.reply.ok,true);assert.equal(out.row,null);assert.equal(out.deleteComment.id,5);
 assert.equal(out.deleteComment.contextJson,comment.contextJson);assert.equal(out.reply.commentId,null);assert.equal(out.reply.total,1);assert.equal(out.reply.loved,1);
 const again=reviewOperation({...base,rows:[config,vote,post],body:{...body,op:'forget_comment',expectedCommentId:'80'}});
 assert.equal(again.reply.ok,true);assert.equal(again.deleteComment,undefined);
});
test('changed or foreign comment references cannot be deleted',()=>{
 const changed=reviewOperation({...base,body:{...body,op:'forget_comment',expectedCommentId:'81'}});
 assert.equal(changed.reply.error,'comment_reference_changed');assert.equal(changed.deleteComment,undefined);
 const foreign=reviewOperation({...base,body:{...body,userId:'11',op:'forget_comment',expectedCommentId:'80'}});
 assert.equal(foreign.deleteComment,undefined);assert.equal(JSON.parse(comment.contextJson).messageId,'80');
});
test('only owner can restore a main post and the original identity must still match',()=>{
 const snapshot=reviewOperation({...base,body:{...body,op:'restore_snapshot'}});
 assert.equal(snapshot.reply.ok,true);assert.deepEqual(snapshot.reply.votes.map(x=>[x.userId,x.vote]),[['10','loved']]);
 assert.equal(reviewOperation({...base,body:{...body,userId:'11',op:'restore_snapshot'}}).reply.error,'denied');
 const replacement={...body,op:'bind',threadId:'61',messageId:'71',messageChannelId:'61',expectedPostMessageId:'70',expectedPostThreadId:'60',expectedMediaKey:'tv:90'};
 const out=reviewOperation({...base,body:replacement});assert.equal(out.reply.ok,true);assert.equal(out.reply.post.messageId,'71');assert.equal(out.postOriginal.contextJson,post.contextJson);assert.equal(out.reply.total,1);
 assert.equal(reviewOperation({...base,body:{...replacement,userId:'11'}}).reply.error,'post_conflict');
 assert.equal(reviewOperation({...base,body:{...replacement,expectedPostMessageId:'99'}}).reply.error,'post_conflict');
});
