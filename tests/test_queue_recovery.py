import json
import asyncio
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from snake_media.notifications import NotificationTransport, NotificationDelivery
from snake_media.delivery_journal import DeliveryJournal

ROOT = Path(__file__).resolve().parents[1]


class QueueCursorTests(unittest.IsolatedAsyncioTestCase):
    async def test_transport_advances_and_wraps_poll_cursor(self):
        requests = []
        responses = iter([{'version': 1, 'notifications': [], 'nextCursor': '1010'},
                          {'version': 1, 'notifications': [], 'nextCursor': None},
                          {'version': 1, 'notifications': []}])
        class Transport(NotificationTransport):
            async def _post(self, body):
                requests.append(body)
                return next(responses)
        transport = Transport('http://unused', 'test')
        for _ in range(3):
            await transport.poll(exclude=['old'])
        self.assertEqual(requests[1].get('afterNotificationId'), '1010')
        self.assertNotIn('afterNotificationId', requests[0])
        self.assertNotIn('afterNotificationId', requests[2])

    async def test_invalid_cursor_is_rejected_without_poisoning_next_request(self):
        requests = []
        responses = iter([{'notifications': [], 'nextCursor': '1010'},
                          {'notifications': [], 'nextCursor': 'not-an-id'},
                          {'notifications': [], 'nextCursor': None}])
        class Transport(NotificationTransport):
            async def _post(self, body):
                requests.append(body)
                return next(responses)
        transport = Transport('http://unused', 'test')
        await transport.poll()
        with self.assertRaises(ValueError):
            await transport.poll()
        await transport.poll()
        self.assertEqual(requests[2]['afterNotificationId'], '1010')

    @unittest.skipUnless(shutil.which('node'), 'Node is required to exercise embedded workflow code')
    async def test_actual_queue_delivers_new_notice_during_ack_outage_without_duplicates_after_restart(self):
        keys = [f'discord:old:{i}' for i in range(1010)]
        rows = [{'id': i+1, 'notificationKey': key, 'destinationId': '333',
                 'payloadJson': json.dumps({'userId': '111', 'messageId': '444', 'text': 'Ready'})}
                for i, key in enumerate(keys + ['discord:new'])]
        script = """const fs=require('fs');const ws=JSON.parse(fs.readFileSync('config-templates/n8n-current-media-workflows.json'));
const w=ws.find(w=>w.id==='snakeNotificationQueueV1'),n=Object.fromEntries(w.nodes.map(n=>[n.name,n]));
let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{const x=JSON.parse(s);
const action=new Function('$input',n['Validate Queue Action'].parameters.jsCode)({first:()=>({json:{body:x.body}})})[0].json;
const result=new Function('$','$input',n['Queue Batch'].parameters.jsCode)(name=>({first:()=>({json:action}),all:()=>name==='Pending Discord Notices'?x.rows.map(json=>({json})):[]}),{all:()=>x.rows.map(json=>({json}))})[0].json;
process.stdout.write(JSON.stringify(result));});"""
        class Transport(NotificationTransport):
            async def _post(self, body):
                if body['action'] == 'ack':
                    raise OSError('acknowledgements unavailable')
                result = await asyncio.to_thread(subprocess.run, ['node', '-e', script], cwd=ROOT,
                    input=json.dumps({'rows': rows, 'body': body}), text=True, capture_output=True, check=True)
                return json.loads(result.stdout)
        sent = []
        async def send(channel, message, text, **options):
            sent.append(text)
            return '555'
        with tempfile.TemporaryDirectory() as folder, DeliveryJournal(Path(folder) / 'journal.sqlite') as journal:
            for key in keys:
                journal.record(key, '555')
            for _ in range(2):  # Recreate both components to exercise restart recovery.
                delivery = NotificationDelivery(Transport('http://unused', 'test'), send, {'111'}, {'333'}, journal=journal)
                with self.assertLogs('snake_media', level='WARNING'):
                    for _ in range(3):
                        await delivery.tick()
            self.assertEqual(sent, ['Ready'])
            self.assertEqual(journal.get('discord:new'), '555')


class QueueOverlayTests(unittest.TestCase):
    def test_overlay_is_idempotent_and_preserves_unrelated_queue_configuration(self):
        spec = importlib.util.spec_from_file_location('queue_recovery', ROOT / 'n8n/notification-efficiency/recovery.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = json.loads((ROOT / 'config-templates/n8n-current-media-workflows.json').read_text())
        queue = next(w for w in source if w['id'] == 'snakeNotificationQueueV1')
        queue['privateMetadata'] = {'endpoint': 'http://private.example', 'secret': 'synthetic-test'}
        original = json.loads(json.dumps(source))
        result = module.build(source)
        self.assertEqual(source, original)
        self.assertEqual(result, module.build(result))
        for before, after in zip(source, result):
            if before['id'] == 'snakeNotificationQueueV1':
                for name in ('Validate Queue Action', 'Queue Batch', 'Collect Preferred Queue'):
                    next(n for n in after['nodes'] if n['name'] == name)['parameters']['jsCode'] = next(
                        n for n in before['nodes'] if n['name'] == name)['parameters']['jsCode']
                next(n for n in after['nodes'] if n['name'] == 'Acknowledge Discord Notice')['parameters']['columns']['value']['deliveredMessageId'] = next(
                    n for n in before['nodes'] if n['name'] == 'Acknowledge Discord Notice')['parameters']['columns']['value']['deliveredMessageId']
            self.assertEqual(before, after)
