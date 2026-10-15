import asyncio,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,MagicMock,patch
import discord
from snake_media.media_reviews import ReviewController,ReviewJournal,review_embed


class ReviewCatalogTests(unittest.IsolatedAsyncioTestCase):
    def test_availability_is_separate_from_the_rating_and_has_a_verified_time(self):
        for state,label in [('available','Available in Jellyfin'),('unavailable','No longer on the server'),('delayed','Availability check delayed')]:
            embed=review_embed({'title':'A','summary':'The couch approves','availability':{'state':state,'mediaType':'movie','checkedAt':1792094400000}},'tag')
            self.assertIn(label,embed.description);self.assertIn('The couch approves',embed.description);self.assertIn('<t:',embed.description)
        embed=review_embed({'title':'A','availability':{'state':'available','mediaType':'tv','checkedAt':1792094400000}},'tag')
        self.assertIn('Episodes available',embed.description)
        embed=review_embed({'title':'A','availability':{'state':'delayed','lastKnown':'available','mediaType':'movie','checkedAt':1792094400000}},'tag')
        self.assertIn('Last confirmed: available',embed.description)

    async def test_ensure_existing_zero_vote_post_binds_without_a_review_comment(self):
        data={'ok':True,'channelId':'40','mediaKey':'tv:90','title':'A','summary':'Awaiting reviews','total':0,
              'post':{'threadId':'60','messageId':'70','messageChannelId':'40'}}
        destination=MagicMock(spec=discord.TextChannel);destination.guild=SimpleNamespace(id=20,me=object())
        destination.permissions_for.return_value=SimpleNamespace(**{k:True for k in ['view_channel','send_messages','read_message_history','embed_links','send_messages_in_threads','create_public_threads']})
        starter=SimpleNamespace(author=SimpleNamespace(id=999),edit=AsyncMock())
        destination.fetch_message=AsyncMock(return_value=starter);destination.send=AsyncMock()
        thread=SimpleNamespace(name='A',archived=False,send=AsyncMock())
        backend=SimpleNamespace(review=AsyncMock(return_value=data))
        client=SimpleNamespace(service=SimpleNamespace(backend=backend),user=SimpleNamespace(id=999),get_channel=lambda i:thread if i==60 else destination)
        with tempfile.TemporaryDirectory() as folder,ReviewJournal(Path(folder)/'r.sqlite3') as journal:
            result=await ReviewController(client,journal).ensure_post({'guildId':'20','userId':'10','channelId':'30'},data)
        self.assertEqual(result[0]['total'],0);thread.send.assert_not_awaited();destination.send.assert_not_awaited()
        self.assertEqual([call.args[0]['op'] for call in backend.review.await_args_list],['bind'])

    async def test_worker_serializes_publication_and_acks_only_after_editing(self):
        from snake_media.review_catalog import ReviewCatalogWorker
        job={'mediaKey':'movie:90','leaseId':'x','fingerprint':'f'}
        backend=SimpleNamespace(catalog=AsyncMock(side_effect=[{'ok':True,'jobs':[job]},{'ok':True}]))
        starter=SimpleNamespace(edit=AsyncMock());thread=SimpleNamespace(name='A',edit=AsyncMock())
        data={'ok':True,'title':'A','mediaKey':'movie:90','channelId':'40','summary':'Awaiting reviews'}
        controller=SimpleNamespace(locks={},call=AsyncMock(return_value=data),ensure_post=AsyncMock(return_value=(data,thread,starter)))
        client=SimpleNamespace(service=SimpleNamespace(backend=backend),reviews=controller)
        worker=ReviewCatalogWorker(client)
        await worker.tick({'userId':'10','guildId':'20','channelId':'30'})
        controller.ensure_post.assert_awaited_once();starter.edit.assert_awaited_once()
        self.assertEqual(backend.catalog.await_args_list[-1].args[0]['action'],'ack');self.assertTrue(backend.catalog.await_args_list[-1].args[0]['ok'])
        self.assertIn('20:movie:90',controller.locks)

    async def test_missing_registered_post_is_reported_without_creating_a_replacement(self):
        from snake_media.review_catalog import ReviewCatalogWorker
        backend=SimpleNamespace(catalog=AsyncMock(side_effect=[{'ok':True,'jobs':[{'mediaKey':'movie:90','leaseId':'x','fingerprint':'f'}]},{'ok':True}]))
        missing=discord.NotFound(SimpleNamespace(status=404,reason='Not Found'),{'code':10003,'message':'Unknown Channel'})
        controller=SimpleNamespace(locks={},call=AsyncMock(return_value={'mediaKey':'movie:90'}),ensure_post=AsyncMock(side_effect=missing))
        client=SimpleNamespace(service=SimpleNamespace(backend=backend),reviews=controller)
        with self.assertLogs('snake_media',level='WARNING'):await ReviewCatalogWorker(client).tick({'userId':'10','guildId':'20','channelId':'30'})
        ack=backend.catalog.await_args_list[-1].args[0];self.assertFalse(ack['ok']);self.assertEqual(ack['error'],'missing_post')
