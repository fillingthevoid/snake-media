import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
from snake_media.media_reviews import review_post_view,review_request_view,ReviewController
from snake_media.n8n_client import format_result
from snake_media.confirmations import presentation
from snake_media.card_registry import CardRegistry
from test_request_commands import client,interaction

class ReviewEntryTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistent_post_and_private_chooser_have_separate_identities(self):
        post=review_post_view();chooser=review_request_view('7','tv:90')
        self.assertIsNone(post.timeout)
        self.assertEqual([b.custom_id for b in post.children],['snake_review_post:loved','snake_review_post:not_for_me'])
        self.assertEqual([b.custom_id for b in chooser.children],['snake_review_request:7:tv:90:loved','snake_review_request:7:tv:90:not_for_me'])
        with self.assertRaises(ValueError):review_request_view('7','tv:wrong')

    async def test_available_request_review_opens_privately_without_consuming_original(self):
        bot,backend=client();backend.review=AsyncMock(return_value={'ok':True,'mediaKey':'tv:90','title':'A'})
        i,message=interaction();i.type=discord.InteractionType.component;i.data={'custom_id':'snake:7:mr_review'}
        message.author=SimpleNamespace(id=123);i.message=message;i.application_id=123;i.token='test-token'
        i.followup.send.return_value=SimpleNamespace(id=999)
        try:
            await bot.on_interaction(i)
            self.assertEqual(backend.review.await_args.args[0]['op'],'open')
            self.assertEqual(backend.review.await_args.args[0]['myRequestsId'],'7')
            self.assertTrue(i.followup.send.await_args.kwargs['ephemeral'])
            self.assertEqual(i.followup.send.await_args.kwargs['view'].children[0].custom_id,'snake_review_request:7:tv:90:loved')
            message.edit.assert_not_awaited()
        finally:await bot.close()

    async def test_starter_buttons_do_not_expire_and_still_validate_registered_identity(self):
        bot,backend=client();bot.reviews.vote=AsyncMock(return_value='Saved')
        i,message=interaction();i.type=discord.InteractionType.component;i.data={'custom_id':'snake_review_post:not_for_me'}
        message.author=SimpleNamespace(id=123);i.message=message
        with tempfile.TemporaryDirectory() as folder,CardRegistry(Path(folder)/'c.sqlite3') as cards:
            bot.card_registry=cards;cards.track('333',str(message.id),'111',now=0,lifetime=300)
            try:
                await bot.on_interaction(i)
                body,vote=bot.reviews.vote.await_args.args
                self.assertEqual(body['postMessageId'],str(message.id));self.assertEqual(vote,'not_for_me')
                self.assertTrue(i.followup.send.await_args.kwargs['ephemeral']);message.edit.assert_not_awaited()
            finally:await bot.close()

    async def test_foreign_starter_message_cannot_submit_a_review(self):
        bot,_=client();bot.reviews.vote=AsyncMock()
        i,message=interaction();i.type=discord.InteractionType.component;i.data={'custom_id':'snake_review_post:loved'}
        message.author=SimpleNamespace(id=999);i.message=message
        try:
            await bot.on_interaction(i);bot.reviews.vote.assert_not_awaited()
            self.assertIn('review post',i.followup.send.await_args.args[0])
        finally:await bot.close()

    async def test_review_choice_passes_captured_identity_and_publishes_from_saved_vote(self):
        backend=SimpleNamespace(review=AsyncMock(return_value={'ok':True,'mediaKey':'tv:90','channelId':'40','title':'A'}))
        controller=ReviewController(SimpleNamespace(service=SimpleNamespace(backend=backend,allowed_users={'10'})),None)
        controller.publish=AsyncMock()
        await controller.vote({'userId':'10','channelId':'30','guildId':'20','myRequestsId':'7','expectedMediaKey':'tv:90'},'loved')
        self.assertEqual(backend.review.await_args_list[0].args[0]['op'],'vote')
        self.assertEqual(backend.review.await_count,1)
        self.assertEqual(backend.review.await_args_list[-1].args[0]['expectedMediaKey'],'tv:90')
        self.assertNotIn('myRequestsId',controller.publish.await_args.args[0])

    async def test_review_action_survives_the_versioned_discord_response_boundary(self):
        reply=format_result({'version':1,'status':'confirmation','pendingId':'7','text':'A',
            'choices':[{'label':'Review','action':'mr_review'}]})
        self.assertEqual(presentation(reply)['view'].children[0].custom_id,'snake:7:mr_review')

    async def test_upgrade_edits_only_bot_authored_registered_posts(self):
        posts={'ok':True,'posts':[{'messageChannelId':'40','messageId':'70'},{'messageChannelId':'40','messageId':'71'}],'nextCursor':None}
        backend=SimpleNamespace(review=AsyncMock(return_value=posts))
        own=SimpleNamespace(author=SimpleNamespace(id=999),edit=AsyncMock())
        foreign=SimpleNamespace(author=SimpleNamespace(id=888),edit=AsyncMock())
        channel=SimpleNamespace(fetch_message=AsyncMock(side_effect=[own,foreign]),send=AsyncMock())
        c=SimpleNamespace(service=SimpleNamespace(backend=backend),user=SimpleNamespace(id=999),get_channel=lambda _:channel)
        controller=ReviewController(c,None)
        with self.assertLogs('snake_media',level='WARNING'):
            result=await controller.upgrade_posts({'userId':'10','channelId':'30','guildId':'20'})
        self.assertEqual(result,{'updated':1,'failed':1})
        self.assertEqual(set(own.edit.await_args.kwargs),{'view','allowed_mentions'})
        foreign.edit.assert_not_awaited();channel.send.assert_not_awaited()
