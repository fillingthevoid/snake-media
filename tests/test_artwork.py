import unittest
from snake_media.n8n_client import format_result
from snake_media.requests import MediaRequest

class ArtworkTests(unittest.TestCase):
    def test_artwork_is_optional_and_only_public_metadata_https_is_accepted(self):
        base = {'version':1,'status':'added','mediaType':'movie','title':'The Matrix','searchStarted':True}
        result = format_result(base | {'posterUrl':'https://image.tmdb.org/t/p/w500/abc.jpg'})
        self.assertEqual(getattr(result, 'poster_url', None), 'https://image.tmdb.org/t/p/w500/abc.jpg')
        self.assertIn('Added to Radarr', result)
        for url in ['http://image.tmdb.org/a.jpg','https://127.0.0.1/a','https://image.tmdb.org.evil.test/a','https://u:p@image.tmdb.org/a','file:///a',None]:
            self.assertIsNone(getattr(format_result(base | {'posterUrl':url}), 'poster_url', None))

    def test_original_message_identity_is_transmitted(self):
        request = MediaRequest('add Matrix','111','person','333','444',message_id='1554232153489805399',requested_at='2026-09-29T00:00:00.000Z')
        self.assertEqual(request.to_payload()['messageId'],'1554232153489805399')
        self.assertEqual(request.to_payload()['requestedAt'],'2026-09-29T00:00:00.000Z')

class ArtworkGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_poster_reply_has_no_mentions_and_includes_original_identity(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from snake_media.bot import SnakeMediaClient
        from snake_media.service import RequestService
        from test_core import config
        seen=[]
        class Backend:
            async def submit(self, request):
                seen.append(request.to_payload())
                return format_result({'version':1,'status':'already_added','mediaType':'movie','title':'Matrix','posterUrl':'https://image.tmdb.org/t/p/w500/a.jpg'})
        c=SnakeMediaClient(RequestService(config(),Backend()))
        c._connection.user=SimpleNamespace(id=999)
        m=SimpleNamespace(id=1554232153489805399,content='<@999> Matrix',webhook_id=None,author=SimpleNamespace(id=111,name='person',bot=False),channel=SimpleNamespace(id=333),guild=SimpleNamespace(id=444),reply=AsyncMock())
        await c.on_message(m)
        self.assertEqual(seen[0]['messageId'],'1554232153489805399')
        self.assertTrue(seen[0]['requestedAt'].endswith('Z'))
        self.assertEqual(m.reply.call_args.kwargs['embed'].thumbnail.url,'https://image.tmdb.org/t/p/w500/a.jpg')
        self.assertEqual(m.reply.call_args.kwargs['allowed_mentions'].to_dict()['parse'],[])
        await c.close()
