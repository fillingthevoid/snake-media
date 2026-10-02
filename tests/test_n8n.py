import asyncio
import unittest

from aiohttp import web
from aiohttp.test_utils import TestServer

from snake_media.config import Config, ConfigError
from snake_media.n8n_client import N8NClient, N8NError, format_result
from snake_media.requests import MediaRequest


REQUEST = MediaRequest('add Matrix', '111', 'person', '333', '444')
BASE_ENV = {'DISCORD_TOKEN': 'dummy', 'ALLOWED_DISCORD_USER_IDS': '111',
            'ALLOWED_DISCORD_CHANNEL_IDS': '333', 'BOT_MODE': 'n8n',
            'N8N_WEBHOOK_URL': 'http://n8n:5678/webhook/discord',
            'N8N_WEBHOOK_SECRET': 'dummy-shared-secret'}


class N8NConfigTests(unittest.TestCase):
    def test_mode_requires_valid_endpoint_and_secret(self):
        settings = Config.from_env(BASE_ENV)
        self.assertEqual(settings.bot_mode, 'n8n')
        self.assertEqual(settings.n8n_timeout_seconds, 60)
        self.assertNotIn('dummy-shared-secret', repr(settings))
        self.assertNotIn('/webhook/discord', repr(settings))
        for key, value in [('BOT_MODE', 'typo'), ('N8N_WEBHOOK_URL', ''),
                           ('N8N_WEBHOOK_URL', 'file:///tmp/test'),
                           ('N8N_WEBHOOK_URL', 'http://user:pass@n8n/test'),
                           ('N8N_WEBHOOK_URL', 'http://n8n/test#fragment'),
                           ('N8N_WEBHOOK_SECRET', ''),
                           ('N8N_WEBHOOK_SECRET', 'bad\r\nheader'),
                           ('N8N_TIMEOUT_SECONDS', 'nan'),
                           ('N8N_TIMEOUT_SECONDS', '0')]:
            with self.subTest(key=key, value=value), self.assertRaises(ConfigError):
                Config.from_env(BASE_ENV | {key: value})


class ResultTests(unittest.TestCase):
    def test_explicit_success_and_search_status(self):
        existing = format_result({'version': 1, 'status': 'already_added',
                                  'mediaType': 'tv', 'title': 'Severance'})
        self.assertIn('Already in Sonarr', existing)
        added = format_result({'version': 1, 'status': 'added', 'mediaType': 'movie',
                               'title': '**Matrix**', 'searchStarted': False})
        self.assertIn('Added to Radarr', added)
        self.assertNotIn('Search started', added)
        self.assertIn(r'\*\*Matrix\*\*', added)
        started = format_result({'version': 1, 'status': 'added', 'mediaType': 'tv',
                                 'title': 'Severance', 'searchStarted': True})
        self.assertIn('Search started', started)

    def test_bad_response_never_becomes_success(self):
        for data in ([], {}, {'version': 1, 'status': 'surprise'},
                     {'version': True, 'status': 'error'},
                     {'version': 1, 'status': 'added', 'mediaType': 'tv', 'title': 'X'},
                     {'version': 1, 'status': 'already_added', 'mediaType': 'tv', 'title': ''}):
            with self.subTest(data=data), self.assertRaises(N8NError):
                format_result(data)

    def test_non_success_uses_safe_local_text(self):
        for status in ('clarification', 'not_found', 'error'):
            text = format_result({'version': 1, 'status': status, 'message': 'secret stack trace'})
            self.assertNotIn('secret', text)
            self.assertNotIn('Added to', text)


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received = []
        self.behavior = 'ok'
        app = web.Application()
        app.router.add_post('/request', self.handle)
        self.server = TestServer(app)
        await self.server.start_server()
        self.client = N8NClient(str(self.server.make_url('/request')), 'test-secret', 0.1)
        await self.client.__aenter__()

    async def asyncTearDown(self):
        await self.client.__aexit__(None, None, None)
        await self.server.close()

    async def handle(self, request):
        self.received.append((await request.json(), request.headers.get('X-Snake-Media-Key')))
        if self.behavior == 'timeout':
            await asyncio.sleep(0.25)
        if self.behavior == 'invalid':
            return web.Response(text='private backend details', content_type='application/json')
        if self.behavior == 'large':
            return web.Response(body=b' ' * 70000, content_type='application/json')
        if self.behavior == 'redirect':
            return web.Response(status=307, headers={'Location': '/request'})
        if self.behavior == 'error':
            return web.Response(status=500, text='private backend details')
        return web.json_response({'version': 1, 'status': 'already_added',
                                  'mediaType': 'movie', 'title': 'The Matrix'})

    async def test_sends_exact_payload_and_auth_header(self):
        self.assertIn('Already in Radarr', await self.client.submit(REQUEST))
        self.assertEqual(self.received, [({'source': 'discord', 'text': 'add Matrix',
                         'userId': '111', 'username': 'person', 'channelId': '333',
                         'guildId': '444'}, 'test-secret')])

    async def test_invalid_large_redirect_and_error_responses_fail_without_retry(self):
        for behavior in ('invalid', 'large', 'redirect', 'error'):
            self.behavior = behavior
            self.received.clear()
            with self.subTest(behavior=behavior), self.assertLogs('snake_media', level='ERROR') as logs:
                with self.assertRaises(N8NError):
                    await self.client.submit(REQUEST)
                self.assertNotIn('private backend', ' '.join(logs.output))
                self.assertNotIn('test-secret', ' '.join(logs.output))
            self.assertEqual(len(self.received), 1)

    async def test_timeout_does_not_retry_or_claim_failure_to_add(self):
        self.behavior = 'timeout'
        with self.assertLogs('snake_media', level='ERROR'):
            reply = await self.client.submit(REQUEST)
        self.assertIn('may still be processing', reply)
        self.assertEqual(len(self.received), 1)

    async def test_cancellation_propagates(self):
        self.behavior = 'timeout'
        task = asyncio.create_task(self.client.submit(REQUEST))
        await asyncio.sleep(0.02)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
