import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
from snake_media.media_reviews import ReviewController,review_embed,marker

POSTER='https://image.tmdb.org/t/p/w500/a.jpg'

class ReviewPosterTests(unittest.IsolatedAsyncioTestCase):
    def test_main_poster_and_text_fallback_preserve_verdict_and_identity(self):
        embed=review_embed({'title':'A','summary':'The couch approves','posterUrl':POSTER},'tag')
        self.assertEqual(embed.image.url,POSTER)
        self.assertFalse(embed.thumbnail.url)
        self.assertIn('The couch approves',embed.description);self.assertEqual(embed.footer.text,'tag')
        for url in [None,'https://image.tmdb.org/a.jpg?key=secret','http://192.168.0.200/a.jpg']:
            fallback=review_embed({'title':'A','summary':'The couch approves','posterUrl':url},'tag')
            self.assertFalse(fallback.image.url);self.assertIn('The couch approves',fallback.description)

    async def test_artwork_upgrade_preserves_starter_and_never_votes_or_creates_posts(self):
        tag=marker('post','20','40','movie:90')
        embed=discord.Embed(title='Original title',description='Original verdict')
        embed.set_footer(text=tag);embed.set_thumbnail(url=POSTER)
        own=SimpleNamespace(author=SimpleNamespace(id=999),embeds=[embed],edit=AsyncMock())
        foreign=SimpleNamespace(author=SimpleNamespace(id=888),embeds=[embed],edit=AsyncMock())
        channel=SimpleNamespace(fetch_message=AsyncMock(side_effect=[own,foreign]),send=AsyncMock())
        posts=[{'channelId':'40','mediaKey':'movie:90','messageChannelId':'60','messageId':mid} for mid in ['70','71']]
        async def backend_call(body):
            if body['op']=='posts':return {'ok':True,'posts':posts,'nextCursor':None}
            self.assertEqual(body['op'],'artwork');self.assertEqual(body['postMessageId'],'70');self.assertEqual(body['channelId'],'60')
            return {'ok':True,'posterUrl':POSTER}
        backend=SimpleNamespace(review=AsyncMock(side_effect=backend_call))
        client=SimpleNamespace(service=SimpleNamespace(backend=backend),user=SimpleNamespace(id=999),get_channel=lambda _:channel)
        with self.assertLogs('snake_media',level='WARNING'):
            result=await ReviewController(client,None).upgrade_posts({'userId':'10','channelId':'30','guildId':'20'},posters=True)
        self.assertEqual(result,{'updated':1,'failed':1,'missing_artwork':0})
        edited=own.edit.await_args.kwargs['embed']
        self.assertEqual(edited.title,'Original title');self.assertEqual(edited.description,'Original verdict');self.assertEqual(edited.footer.text,tag)
        self.assertEqual(edited.image.url,POSTER);self.assertFalse(edited.thumbnail.url)
        self.assertEqual(len(own.edit.await_args.kwargs['view'].children),2)
        self.assertEqual(embed.thumbnail.url,POSTER)
        foreign.edit.assert_not_awaited();channel.send.assert_not_awaited()

    async def test_missing_artwork_keeps_existing_image_and_skips_edit(self):
        embed=discord.Embed();embed.set_footer(text=marker('post','20','40','movie:90'));embed.set_image(url=POSTER)
        message=SimpleNamespace(author=SimpleNamespace(id=999),embeds=[embed],edit=AsyncMock())
        channel=SimpleNamespace(fetch_message=AsyncMock(return_value=message))
        backend=SimpleNamespace(review=AsyncMock(side_effect=[{'ok':True,'posts':[{'channelId':'40','mediaKey':'movie:90','messageChannelId':'60','messageId':'70'}],'nextCursor':None},{'ok':True,'posterUrl':None}]))
        client=SimpleNamespace(service=SimpleNamespace(backend=backend),user=SimpleNamespace(id=999),get_channel=lambda _:channel)
        result=await ReviewController(client,None).upgrade_posts({'userId':'10','channelId':'30','guildId':'20'},posters=True)
        self.assertEqual(result,{'updated':0,'failed':0,'missing_artwork':1});message.edit.assert_not_awaited()
