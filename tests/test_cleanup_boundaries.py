import importlib.util
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from snake_media.bot import SnakeMediaClient
from snake_media.card_registry import CardRegistry
from snake_media.confirmations import bounded_content, discord_length
from snake_media.service import RequestService
from test_core import config

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cleanup_watchdog', ROOT / 'n8n/lock-recovery/watchdog.py')
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)


class CleanupFingerprintTests(unittest.TestCase):
    def blocking_count(self, content):
        with tempfile.TemporaryDirectory() as folder, sqlite3.connect(':memory:') as connection:
            node = Path(folder) / 'node.js'
            node.write_bytes(content)
            connection.executescript('''CREATE TABLE execution_entity(id INTEGER,workflowId TEXT,status TEXT,startedAt TEXT,stoppedAt TEXT,deletedAt TEXT);
                INSERT INTO execution_entity VALUES (1,'snakeTelegramControlsRetryV1','running','2026-10-01T10:00:00Z',NULL,NULL);
                CREATE TABLE execution_data(executionId INTEGER,data TEXT);
                CREATE TABLE workflow_entity(id TEXT,nodes TEXT);''')
            shape = [{'type': 'n8n-nodes-base.scheduleTrigger', 'parameters': {}},
                     {'type': 'CUSTOM.snakeTelegramControls', 'parameters': {'operation': 'retry'}}]
            connection.execute('INSERT INTO workflow_entity VALUES (?,?)', ('snakeTelegramControlsRetryV1', json.dumps(shape)))
            with patch.object(watchdog, 'Path', return_value=node):
                return watchdog.activity_count(connection, time.time())

    def test_lf_and_crlf_cleanup_copies_prove_the_same_safe_implementation(self):
        content = (ROOT / 'n8n/button-feedback/custom/SnakeTelegramControls.node.js').read_bytes().replace(b'\r\n', b'\n')
        for variant in (content, content.replace(b'\n', b'\r\n')):
            with self.subTest(crlf=b'\r\n' in variant):
                self.assertEqual(self.blocking_count(variant), 0)

    def test_changed_cleanup_code_remains_blocking(self):
        content = (ROOT / 'n8n/button-feedback/custom/SnakeTelegramControls.node.js').read_bytes()
        self.assertEqual(self.blocking_count(content + b'\nthrow Error("changed code");\n'), 1)


class ExpiryContentTests(unittest.IsolatedAsyncioTestCase):
    async def test_emoji_expiry_edits_fit_budget_and_finish_public_and_webhook_cleanup(self):
        for private in (False, True):
            with self.subTest(private=private), tempfile.TemporaryDirectory() as folder, CardRegistry(Path(folder) / 'cards.sqlite') as cards:
                client = SnakeMediaClient(RequestService(config(), SimpleNamespace()), card_registry=cards)
                client._connection.user = SimpleNamespace(id=999)
                content = bounded_content('😀' * 1800)
                self.assertEqual(discord_length(content), 1999)
                edits = []
                async def edit(*args, **options):
                    if discord_length(options['content']) > 2000:
                        raise ValueError('oversized expiry edit')
                    edits.append(options)
                message = SimpleNamespace(author=SimpleNamespace(id=999), content=content, components=[], edit=edit)
                client.get_channel = lambda _: SimpleNamespace(fetch_message=AsyncMock(return_value=message))
                cards.track('333', '100', '111', now=time.time()-301,
                    webhook_id='999' if private else None, webhook_token='synthetic' if private else None)
                webhook = SimpleNamespace(fetch_message=AsyncMock(return_value=message), edit_message=edit)
                try:
                    with patch('snake_media.bot.discord.Webhook.partial', return_value=webhook):
                        await client.cleanup_cards()
                    self.assertEqual(len(edits), 1)
                    self.assertLessEqual(discord_length(edits[0]['content']), 2000)
                    self.assertTrue(edits[0]['content'].endswith('Menu expired. Use /help or /status to reopen.'))
                    self.assertIsNone(edits[0]['view'])
                    self.assertFalse(cards.queued('333', '100'))
                    self.assertIsNone(cards.control('333', '100'))
                finally:
                    await client.close()
