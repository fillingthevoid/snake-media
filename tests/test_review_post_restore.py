import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,MagicMock
import discord
from snake_media.media_reviews import ReviewController,ReviewJournal

class ReviewPostRestoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_confirmed_missing_registered_post_is_recreated_without_new_votes(self):
        from snake_media.review_post_restore import restore_post
        old={'channelId':'40','messageChannelId':'60','messageId':'70','threadId':'60','mediaKey':'movie:90'}
        data={'ok':True,'channelId':'40','mediaKey':'movie:90','title':'A','summary':'One loved it','vote':'loved','posterUrl':'https://image.tmdb.org/t/p/w500/a.jpg','votes':[{'userId':'10','vote':'loved'}]}
        calls=[]
        async def backend(body):calls.append(body);return data|{'post':{'threadId':'61','messageId':'71','messageChannelId':'61'}}
        dest=MagicMock(spec=discord.ForumChannel);dest.id=40;dest.guild=SimpleNamespace(id=20,me=object(),fetch_member=AsyncMock(return_value=object()),active_threads=AsyncMock(return_value=[]))
        dest.flags=SimpleNamespace(require_tag=False);dest.threads=[]
        dest.guild.fetch_channels=AsyncMock(return_value=[dest])
        dest.archived_threads.return_value.__aiter__.return_value=[]
        dest.permissions_for.return_value=SimpleNamespace(**{k:True for k in ['view_channel','send_messages','read_message_history','embed_links','add_reactions','send_messages_in_threads']})
        thread=SimpleNamespace(id=61);starter=SimpleNamespace(id=71,channel=SimpleNamespace(id=61))
        dest.create_thread=AsyncMock(return_value=SimpleNamespace(thread=thread,message=starter))
        missing=discord.NotFound(SimpleNamespace(status=404,reason='Not Found'),{'code':10003,'message':'Unknown Channel'})
        partial=MagicMock(spec=discord.ForumChannel);partial.id=40;partial.guild=dest.guild
        partial.flags=SimpleNamespace(require_tag=False)
        partial.permissions_for.return_value=SimpleNamespace(**{k:False for k in ['view_channel','send_messages','read_message_history','embed_links','add_reactions','send_messages_in_threads']})
        async def fetch(cid):
            if cid==60:raise missing
            return partial
        client=SimpleNamespace(user=SimpleNamespace(id=999),get_channel=lambda _:None,fetch_guild=AsyncMock(return_value=dest.guild),fetch_channel=AsyncMock(side_effect=fetch),service=SimpleNamespace(backend=SimpleNamespace(review=AsyncMock(side_effect=backend))))
        with tempfile.TemporaryDirectory() as folder,ReviewJournal(Path(folder)/'r.sqlite3') as journal:
            controller=ReviewController(client,journal);controller.publish=AsyncMock()
            result=await restore_post(controller,{'userId':'10','guildId':'20','channelId':'30'},old)
        self.assertTrue(result['restored']);self.assertEqual(dest.create_thread.await_count,1);self.assertNotIn('vote',[c['op'] for c in calls])
        bind=next(c for c in calls if c['op']=='bind');self.assertEqual(bind['expectedPostMessageId'],'70');self.assertEqual(bind['expectedPostThreadId'],'60')
        self.assertEqual(dest.create_thread.await_args.kwargs['embed'].image.url,data['posterUrl'])
        self.assertEqual(len(dest.create_thread.await_args.kwargs['view'].children),2)
        self.assertIs(controller.publish.await_args.kwargs['member'],dest.guild.fetch_member.return_value)

    async def test_forbidden_original_never_creates_replacement(self):
        from snake_media.review_post_restore import restore_post
        error=discord.Forbidden(SimpleNamespace(status=403,reason='Forbidden'),'Missing Permissions')
        client=SimpleNamespace(get_channel=lambda _:None,fetch_channel=AsyncMock(side_effect=error),service=SimpleNamespace())
        with self.assertRaises(discord.Forbidden):
            await restore_post(ReviewController(client,None),{'userId':'10','guildId':'20','channelId':'30'},{'messageChannelId':'60','messageId':'70'})

    async def test_resume_finishes_saved_comments_without_creating_another_post_or_vote(self):
        from snake_media.review_post_restore import restore_post
        post={'channelId':'40','messageChannelId':'60','messageId':'70','threadId':'60','mediaKey':'movie:90'}
        data={'ok':True,'channelId':'40','mediaKey':'movie:90','title':'A','vote':'loved','votes':[{'userId':'10','vote':'loved'}]}
        dest=MagicMock(spec=discord.ForumChannel);dest.id=40
        member=object();guild=SimpleNamespace(id=20,me=None,fetch_member=AsyncMock(return_value=member),fetch_channels=AsyncMock(return_value=[dest]))
        dest.guild=guild;dest.flags=SimpleNamespace(require_tag=False)
        dest.permissions_for.return_value=SimpleNamespace(**{k:True for k in ['view_channel','send_messages','read_message_history','embed_links','add_reactions','send_messages_in_threads']})
        dest.create_thread=AsyncMock()
        message_channel=SimpleNamespace(fetch_message=AsyncMock(return_value=object()))
        client=SimpleNamespace(user=SimpleNamespace(id=999),get_channel=lambda cid:message_channel if cid==60 else dest,fetch_guild=AsyncMock(return_value=guild),service=SimpleNamespace(backend=SimpleNamespace(review=AsyncMock(return_value=data))))
        with tempfile.TemporaryDirectory() as folder,ReviewJournal(Path(folder)/'r.sqlite3') as journal:
            controller=ReviewController(client,journal);controller.publish=AsyncMock()
            result=await restore_post(controller,{'userId':'10','guildId':'20','channelId':'30'},post,resume=True)
        self.assertFalse(result['restored']);self.assertEqual(result['comments'],1);dest.create_thread.assert_not_awaited()
        self.assertIs(controller.publish.await_args.kwargs['member'],member)
        self.assertNotIn('vote',[c.args[0]['op'] for c in client.service.backend.review.await_args_list])
