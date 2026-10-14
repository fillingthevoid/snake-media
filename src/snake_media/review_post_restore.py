"""Explicit owner maintenance: restore one confirmed missing forum review post."""
import argparse
import asyncio
import logging
import re
from pathlib import Path
import discord
from .config import Config
from .n8n_client import N8NClient
from .service import RequestService
from .media_reviews import ReviewController,ReviewJournal,destination_error,marker,review_embed,review_post_view,review_title

async def restore_post(controller,actor,post,resume=False):
    client=controller.client
    missing=False
    try:
        channel=client.get_channel(int(post['messageChannelId'])) or await client.fetch_channel(int(post['messageChannelId']))
        await channel.fetch_message(int(post['messageId']))
        if not resume:return {'restored':False,'comments':0}
    except discord.NotFound as exc:
        if exc.code not in (10003,10008):raise
        missing=True
    destination=client.get_channel(int(post['channelId'])) or await client.fetch_channel(int(post['channelId']))
    if not isinstance(destination,discord.ForumChannel):raise ValueError('restore_requires_forum')
    # REST-only clients have no Gateway guild/role cache. Fetch the full guild
    # and its channels before deriving effective member permissions.
    guild=await client.fetch_guild(int(actor['guildId']))
    destination=next((c for c in await guild.fetch_channels() if str(c.id)==post['channelId']),None)
    if not isinstance(destination,discord.ForumChannel):raise ValueError('restore_destination_unavailable')
    member=await destination.guild.fetch_member(client.user.id)
    if destination_error(destination,actor['guildId'],member):raise ValueError('review_permissions_missing')
    body=actor|{'channelId':post['messageChannelId'],'postMessageId':post['messageId']}
    await controller.call(body,op='artwork')
    data=await controller.call(body,op='restore_snapshot')
    if data['channelId']!=post['channelId'] or data['mediaKey']!=post['mediaKey']:raise ValueError('review_restore_identity_changed')
    tag=marker('post',actor['guildId'],data['channelId'],data['mediaKey'])
    recovery=marker('restore',actor['guildId'],data['channelId'],data['mediaKey'],post['messageId'])
    if missing:
        threads=[t for t in await destination.guild.active_threads() if t.parent_id==destination.id]
        async for t in destination.archived_threads(limit=100):threads.append(t)
        found=None
        for t in threads:
            if t.owner_id!=client.user.id:continue
            message=await t.fetch_message(t.id)
            if message.author.id==client.user.id and any(e.footer.text==tag for e in message.embeds):found=message;break
        receipt=controller.journal.get(recovery)
        if found:
            replacement={'threadId':str(found.channel.id),'messageId':str(found.id),'messageChannelId':str(found.channel.id)}
        elif receipt is not None:
            raise ValueError('review_restore_outcome_unknown')
        else:
            if not controller.journal.begin(recovery):raise ValueError('review_restore_outcome_unknown')
            tags=[t for t in destination.available_tags if not t.moderated][:1] if destination.flags.require_tag else []
            result=await destination.create_thread(name=review_title(data),embed=review_embed(data,tag),view=review_post_view(),applied_tags=tags,allowed_mentions=discord.AllowedMentions.none())
            replacement={'threadId':str(result.thread.id),'messageId':str(result.message.id),'messageChannelId':str(result.thread.id)}
        controller.journal.save(recovery,replacement)
        await controller.call(body,op='bind',mediaKey=data['mediaKey'],expectedMediaKey=data['mediaKey'],
            expectedPostMessageId=post['messageId'],expectedPostThreadId=post['threadId'],**replacement)
        previous=controller.journal.get(tag)
        if previous and previous!=replacement:controller.journal.forget_deleted(tag,post['messageId'])
        controller.journal.save(tag,replacement)
    else:
        replacement={key:post[key] for key in ('threadId','messageId','messageChannelId')}
    comments=0
    for vote in data.get('votes',[]):
        if not re.fullmatch(r'[1-9][0-9]{0,19}',str(vote.get('userId',''))) or vote.get('vote') not in ('loved','not_for_me'):
            raise ValueError('invalid_saved_review')
        voter=actor|{'userId':vote['userId'],'channelId':replacement['messageChannelId'],'postMessageId':replacement['messageId']}
        saved=await controller.call(voter,op='lookup')
        if saved.get('vote') not in ('loved','not_for_me'):raise ValueError('saved_vote_changed')
        await controller.publish(voter,saved,destination=destination,member=member);comments+=1
    return {'restored':missing,'comments':comments,'messageId':replacement['messageId'],'threadId':replacement['threadId']}

async def run(media_key,resume=False):
    c=Config.from_env()
    if not c.admin_user_ids or not c.allowed_channel_ids:raise ValueError('restore_owner_required')
    async with N8NClient(c.n8n_webhook_url,c.n8n_webhook_secret) as backend:
        async with discord.Client(intents=discord.Intents.none(),allowed_mentions=discord.AllowedMentions.none()) as client:
            await client.login(c.discord_token);client.service=RequestService(c,backend)
            request=await client.fetch_channel(int(sorted(c.allowed_channel_ids,key=int)[0]))
            actor={'userId':sorted(c.admin_user_ids,key=int)[0],'channelId':str(request.id),'guildId':str(request.guild.id)}
            with ReviewJournal(Path(c.notification_state_path).with_name('reviews.sqlite3')) as journal:
                controller=ReviewController(client,journal);cursor=0;matches=[]
                for _ in range(4001):
                    page=await controller.call(actor,op='posts',cursor=cursor)
                    matches.extend(p for p in page['posts'] if p['mediaKey']==media_key)
                    if page.get('nextCursor') is None:break
                    if type(page['nextCursor']) is not int or page['nextCursor']<=cursor:raise ValueError('invalid_review_cursor')
                    cursor=page['nextCursor']
                else:raise ValueError('review_restore_limit')
                if len(matches)!=1:raise ValueError('review_restore_post_not_unique')
                result=await restore_post(controller,actor,matches[0],resume=resume);print('Review post restored:',result['restored'],'saved review comments:',result['comments'])
                return 0

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--media-key',required=True)
    parser.add_argument('--resume',action='store_true',help='Finish saved comment publication on an already restored post')
    args=parser.parse_args()
    if not re.fullmatch(r'(movie|tv):[1-9][0-9]{0,19}',args.media_key):parser.error('Invalid media key')
    for name in ('discord','aiohttp','asyncio'):
        logger=logging.getLogger(name);logger.handlers=[logging.NullHandler()];logger.propagate=False
    try:return asyncio.run(run(args.media_key,resume=args.resume))
    except Exception as exc:print('Review post restore deferred:',type(exc).__name__);return 1

if __name__=='__main__':raise SystemExit(main())
