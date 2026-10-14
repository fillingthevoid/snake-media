import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,MagicMock
import discord
from snake_media import media_reviews as reviews

RATING={'emoji':'🏆','label':'All hiss, no miss'}
POSTER='https://image.tmdb.org/t/p/w500/a.jpg'

class ReviewRatingTitlesTests(unittest.IsolatedAsyncioTestCase):
    def test_heading_and_forum_name_keep_verdict_when_media_title_is_long(self):
        data={'title':'The Matrix','rating':RATING,'summary':'One loved it','posterUrl':POSTER}
        self.assertEqual(reviews.review_embed(data,'tag').title,'🏆 The Matrix — All hiss, no miss')
        self.assertEqual(reviews.review_title(data),'🏆 The Matrix — All hiss, no miss')
        long=reviews.review_title(data|{'title':'A'*200})
        self.assertEqual(len(long),100);self.assertTrue(long.endswith('… — All hiss, no miss'))
        heading=reviews.review_embed(data|{'title':'A'*400},'tag').title
        self.assertEqual(len(heading),250);self.assertTrue(heading.endswith('… — All hiss, no miss'))
        safe=reviews.review_title(data|{'title':'@everyone\nThe Matrix'})
        self.assertNotIn('@everyone',safe);self.assertNotIn('\n',safe)
        self.assertEqual(reviews.review_title({'title':'A','rating':{'emoji':'💬','label':'Awaiting reviews'}}),'💬 A — Awaiting reviews')
        self.assertEqual(reviews.review_title({'title':'A'}),'A')

    def fixture(self,rename_error=None,name='Old title'):
        data={'ok':True,'channelId':'40','mediaKey':'movie:90','title':'The Matrix','summary':'1 loved it',
              'rating':RATING,'vote':'loved','commentId':'80','post':{'threadId':'60','messageId':'60','messageChannelId':'60'}}
        dest=MagicMock(spec=discord.ForumChannel);dest.guild=SimpleNamespace(id=20,me=object());dest.flags=SimpleNamespace(require_tag=False)
        dest.permissions_for.return_value=SimpleNamespace(**{k:True for k in ['view_channel','send_messages','read_message_history','embed_links','add_reactions','send_messages_in_threads']})
        starter=SimpleNamespace(id=60,author=SimpleNamespace(id=999),edit=AsyncMock(),add_reaction=AsyncMock())
        comment=SimpleNamespace(id=80,author=SimpleNamespace(id=999),edit=AsyncMock())
        thread=SimpleNamespace(id=60,owner_id=999,name=name,archived=False,edit=AsyncMock(side_effect=rename_error),fetch_message=AsyncMock(side_effect=lambda mid:starter if mid==60 else comment),send=AsyncMock())
        client=SimpleNamespace(service=SimpleNamespace(backend=SimpleNamespace(review=AsyncMock(return_value=data))),user=SimpleNamespace(id=999),get_channel=lambda cid:dest if cid==40 else thread)
        return data,client,thread,starter

    async def test_vote_publication_updates_heading_and_renames_only_changed_threads(self):
        for name,renames in [('Old title',1),('🏆 The Matrix — All hiss, no miss',0)]:
            data,client,thread,starter=self.fixture(name=name)
            with tempfile.TemporaryDirectory() as folder,reviews.ReviewJournal(Path(folder)/'r.db') as journal:
                await reviews.ReviewController(client,journal).publish({'guildId':'20','userId':'10','channelId':'60','postMessageId':'60'},data)
            self.assertEqual(starter.edit.await_args.kwargs['embed'].title,'🏆 The Matrix — All hiss, no miss')
            self.assertEqual(thread.edit.await_count,renames)
            if renames:self.assertEqual(thread.edit.await_args.kwargs,{'name':'🏆 The Matrix — All hiss, no miss'})
            thread.send.assert_not_awaited()

    async def test_rename_failure_still_updates_heading_and_saved_comment(self):
        error=discord.Forbidden(SimpleNamespace(status=403,reason='Forbidden'),'Missing Permissions')
        data,client,thread,starter=self.fixture(rename_error=error)
        with tempfile.TemporaryDirectory() as folder,reviews.ReviewJournal(Path(folder)/'r.db') as journal:
            with self.assertRaises(discord.Forbidden):
                await reviews.ReviewController(client,journal).publish({'guildId':'20','userId':'10','channelId':'60','postMessageId':'60'},data)
        self.assertEqual(starter.edit.await_args.kwargs['embed'].title,'🏆 The Matrix — All hiss, no miss')
        self.assertEqual(len(starter.edit.await_args.kwargs['view'].children),2)
        self.assertIn('comment',[c.args[0]['op'] for c in client.service.backend.review.await_args_list])

    async def test_title_refresh_preserves_existing_poster_body_and_buttons_without_voting(self):
        data,client,thread,starter=self.fixture()
        tag=reviews.marker('post','20','40','movie:90')
        embed=discord.Embed(title='The Matrix',description='Existing body');embed.set_image(url=POSTER);embed.set_footer(text=tag)
        starter.embeds=[embed]
        post=data['post']|{'channelId':'40','mediaKey':'movie:90'}
        async def backend(body):
            if body['op']=='posts':return {'ok':True,'posts':[post],'nextCursor':None}
            if body['op']=='lookup':return data
            raise AssertionError('Unexpected write')
        client.service.backend.review=AsyncMock(side_effect=backend)
        result=await reviews.ReviewController(client,None).upgrade_posts({'userId':'10','guildId':'20','channelId':'30'},titles=True)
        self.assertEqual(result,{'updated':1,'failed':0})
        edited=starter.edit.await_args.kwargs['embed']
        self.assertEqual(edited.title,'🏆 The Matrix — All hiss, no miss');self.assertEqual(edited.description,'Existing body')
        self.assertEqual(edited.image.url,POSTER);self.assertEqual(edited.footer.text,tag)
        self.assertEqual(len(starter.edit.await_args.kwargs['view'].children),2)
        thread.edit.assert_awaited_once_with(name='🏆 The Matrix — All hiss, no miss')
        self.assertEqual([c.args[0]['op'] for c in client.service.backend.review.await_args_list],['posts','lookup'])

    async def test_uncertain_creation_recovers_marker_under_previous_rating_name(self):
        data,client,thread,starter=self.fixture(name='⚖️ The Matrix — The couch is divided')
        tag=reviews.marker('post','20','40','movie:90')
        starter.channel=thread;starter.embeds=[reviews.review_embed(data,tag)]
        foreign=SimpleNamespace(id=61,owner_id=888,fetch_message=AsyncMock(side_effect=AssertionError('Foreign thread must not be read')))
        dest=client.get_channel(40);dest.threads=[foreign,thread];dest.archived_threads.return_value.__aiter__.return_value=[];dest.create_thread=AsyncMock()
        with tempfile.TemporaryDirectory() as folder,reviews.ReviewJournal(Path(folder)/'r.db') as journal:
            journal.begin(tag)
            await reviews.ReviewController(client,journal).publish({'guildId':'20','userId':'10','channelId':'60','postMessageId':'60'},data|{'post':None})
        dest.create_thread.assert_not_awaited();self.assertEqual(thread.edit.await_args.kwargs['name'],'🏆 The Matrix — All hiss, no miss')

    async def test_explicit_restore_finds_changed_name_without_creating_another_starter(self):
        from snake_media.review_post_restore import restore_post
        data,client,thread,starter=self.fixture(name='⚖️ The Matrix — The couch is divided')
        tag=reviews.marker('post','20','40','movie:90')
        starter.channel=thread;starter.embeds=[reviews.review_embed(data,tag)]
        dest=client.get_channel(40);dest.id=40;dest.create_thread=AsyncMock()
        foreign=SimpleNamespace(id=61,owner_id=888,fetch_message=AsyncMock(side_effect=AssertionError('Foreign thread must not be read')))
        dest.guild.active_threads=AsyncMock(return_value=[foreign,thread]);thread.parent_id=40;foreign.parent_id=40
        dest.guild.fetch_channels=AsyncMock(return_value=[dest]);dest.guild.fetch_member=AsyncMock(return_value=object())
        dest.archived_threads.return_value.__aiter__.return_value=[]
        client.fetch_guild=AsyncMock(return_value=dest.guild)
        original=client.get_channel
        client.get_channel=lambda cid:None if cid==59 else original(cid)
        missing=discord.NotFound(SimpleNamespace(status=404,reason='Not Found'),{'code':10003,'message':'Unknown Channel'})
        client.fetch_channel=AsyncMock(side_effect=missing)
        client.service.backend.review=AsyncMock(return_value=data|{'votes':[]})
        old={'channelId':'40','messageChannelId':'59','messageId':'59','threadId':'59','mediaKey':'movie:90'}
        with tempfile.TemporaryDirectory() as folder,reviews.ReviewJournal(Path(folder)/'r.db') as journal:
            result=await restore_post(reviews.ReviewController(client,journal),{'userId':'10','guildId':'20','channelId':'30'},old)
        self.assertEqual(result['messageId'],'60');dest.create_thread.assert_not_awaited()
        self.assertNotIn('vote',[c.args[0]['op'] for c in client.service.backend.review.await_args_list])
