import importlib.util
from pathlib import Path
import unittest
import threading
import urllib.request
import urllib.error
from unittest.mock import AsyncMock

from snake_media.bot import SnakeMediaClient
from snake_media.service import RequestService
from snake_media.config import Config


class HealthTests(unittest.IsolatedAsyncioTestCase):
    def test_collector_denies_missing_secret_before_probes(self):
        spec=importlib.util.spec_from_file_location('health',Path(__file__).resolve().parents[1]/'tools/server_health.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        from http.server import ThreadingHTTPServer
        from unittest.mock import Mock
        server=ThreadingHTTPServer(('127.0.0.1',0),mod.Handler)
        server.collector=Mock();server.collector.config={'secret':'synthetic-test-secret-only'}
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/health',timeout=2)
            self.assertEqual(error.exception.code,403);server.collector.read.assert_not_called()
        finally:
            server.shutdown();server.server_close();t.join()

    def test_workflow_route_preserves_other_commands_and_has_no_media_writes(self):
        spec=importlib.util.spec_from_file_location('health_build',Path(__file__).resolve().parents[1]/'n8n/server-health/build.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        parent={'id':'HXtTzVTrpNZMZVt3','nodes':[{'name':'Discord Webhook','credentials':{'httpHeaderAuth':{'id':'CONFIGURE_HEADER','name':'Configure Header'}}}], 'connections':{'Confirmation Callback?':{'main':[[],[{'node':'Parse Status Command','type':'main','index':0}]]}}}
        health,patched=mod.build([parent],'http://172.24.0.1:17492/health')
        self.assertEqual(patched['connections']['Server Health Command?']['main'][1][0]['node'],'Parse Status Command')
        self.assertEqual(patched['connections']['Normalize Health Reply']['main'][0][0]['node'],'Respond to Discord')
        probe=next(n for n in health['nodes'] if n['type'].endswith('httpRequest'))
        self.assertEqual(probe['parameters']['method'],'GET')
        self.assertNotIn('Parse Server Health Command',str(parent))
        parser=next(n for n in patched['nodes'] if n['name']=='Parse Server Health Command')
        self.assertIn('$("Validate Discord Request")',parser['parameters']['jsCode'])

    def test_range_requires_exact_success_and_data(self):
        spec=importlib.util.spec_from_file_location('health',Path(__file__).resolve().parents[1]/'tools/server_health.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        self.assertTrue(mod.valid_sample(206,{'Content-Range':'bytes 0-4095/999999','Content-Type':'video/mp4'},b'x'*4096))
        for status,headers,body in [(200,{'Content-Type':'text/html'},b'login'),(206,{'Content-Range':'bytes 1-4096/99999'},b'x'*4096),(206,{'Content-Range':'bytes 0-4095/99999','Content-Type':'application/json'},b'x'*4096)]:
            self.assertFalse(mod.valid_sample(status,headers,body))

    async def test_slash_registration_and_unauthorized_request_never_reaches_backend(self):
        cfg=Config.from_env({'DISCORD_TOKEN':'test','ALLOWED_DISCORD_USER_IDS':'123456789012345678','ALLOWED_DISCORD_CHANNEL_IDS':'234567890123456789'})
        backend=AsyncMock();service=RequestService(cfg,backend);client=SnakeMediaClient(service)
        self.assertIsNotNone(client.tree.get_command('serverstatus'))
        from snake_media.requests import IncomingMessage
        reply=await service.handle(IncomingMessage(text='<@345678901234567890> serverstatus',user_id='456789012345678901',username='test',channel_id='234567890123456789',guild_id='567890123456789012',is_bot=False), '345678901234567890')
        self.assertIn('authorized',reply);backend.submit.assert_not_awaited()
