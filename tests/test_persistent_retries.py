from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from contextlib import closing
import sqlite3
import tempfile
import unittest

from snake_media.delivery_journal import DeliveryJournal
from snake_media.notifications import NotificationDelivery


def row(key):
    return {'notificationKey': key, 'destinationId': '333',
            'payload': {'userId': '111', 'messageId': '444', 'text': 'Ready'}}


class PersistentRetryTests(unittest.IsolatedAsyncioTestCase):
    def test_existing_receipt_database_migrates_without_losing_acknowledgements(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.sqlite3'
            with closing(sqlite3.connect(path)) as db:
                db.execute('CREATE TABLE receipts (notification_key TEXT PRIMARY KEY, message_id TEXT NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0)')
                db.execute("INSERT INTO receipts VALUES ('old','555',0)")
                db.commit()
            with DeliveryJournal(path) as journal:
                self.assertEqual(journal.pending(), {'old': '555'})
                self.assertEqual(journal.retries(), {})
                journal.defer('new', 1, 1060, 1000)
            with DeliveryJournal(path) as journal:
                self.assertEqual(journal.retries()['new'], (1, 1060))
                self.assertEqual(journal.get('old'), '555')

    async def test_restart_keeps_countdown_and_backoff_and_allows_other_delivery(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.sqlite3'
            wall, mono = [1000], [0]
            transport = SimpleNamespace(poll=AsyncMock(return_value=[row('bad')]), acknowledge=AsyncMock())
            send = AsyncMock(side_effect=OSError('offline'))
            with DeliveryJournal(path) as journal:
                worker = NotificationDelivery(transport, send, {'111'}, {'333'}, journal, clock=lambda: mono[0], wall_clock=lambda: wall[0])
                with self.assertLogs('snake_media', level='WARNING'):
                    await worker.tick()
            wall[0], mono[0] = 1030, 500
            transport.poll.return_value = [row('bad'), row('good')]
            send = AsyncMock(return_value='555')
            with DeliveryJournal(path) as journal:
                worker = NotificationDelivery(transport, send, {'111'}, {'333'}, journal, clock=lambda: mono[0], wall_clock=lambda: wall[0])
                await worker.tick()
                send.assert_awaited_once()
                self.assertIn('bad', transport.poll.call_args.kwargs['exclude'])
                wall[0], mono[0] = 1060, 530
                transport.poll.return_value = [row('bad')]
                send.side_effect = OSError('offline')
                with self.assertLogs('snake_media', level='WARNING'):
                    await worker.tick()
                self.assertEqual(journal.retries()['bad'], (2, 1180.0))
            wall[0], mono[0] = 1120, 0
            send = AsyncMock(return_value='556')
            with DeliveryJournal(path) as journal:
                worker = NotificationDelivery(transport, send, {'111'}, {'333'}, journal, clock=lambda: mono[0], wall_clock=lambda: wall[0])
                await worker.tick()
                send.assert_not_awaited()
                wall[0], mono[0] = 1180, 60
                await worker.tick()
                self.assertNotIn('bad', journal.retries())
                self.assertEqual(journal.get('bad'), '556')

    async def test_clock_correction_caps_wait_and_runtime_storage_error_is_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.sqlite3'
            transport = SimpleNamespace(poll=AsyncMock(return_value=[row('bad'), row('good')]), acknowledge=AsyncMock())
            async def send(channel, message, text):
                if calls[0] == 0:
                    calls[0] += 1
                    raise OSError('offline')
                return '555'
            with DeliveryJournal(path) as journal:
                journal.defer('older', 5, 10900, 10000)
                calls = [0]
                worker = NotificationDelivery(transport, send, {'111'}, {'333'}, journal, clock=lambda: 50, wall_clock=lambda: 1000)
                self.assertEqual(worker.retries['older'], (5, 950))
                with patch.object(journal, 'defer', side_effect=OSError('disk full')):
                    with self.assertLogs('snake_media', level='WARNING'):
                        await worker.tick()
                self.assertEqual(journal.get('good'), '555')
                self.assertIn('bad', worker.retries)

    def test_bounded_retry_rows_receipt_cleanup_and_invalid_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.sqlite3'
            with DeliveryJournal(path) as journal:
                journal.record('existing', '555')
                for i in range(1001):
                    journal.defer('notice:' + str(i), 1, 2000 + i, 1000 + i)
                self.assertEqual(len(journal.retries()), 1000)
                self.assertNotIn('notice:0', journal.retries())
                journal.record('notice:1000', '556')
                self.assertNotIn('notice:1000', journal.retries())
                self.assertEqual(journal.get('existing'), '555')
                with self.assertRaises(ValueError):
                    journal.defer('invalid', 0, 2000, 1000)
                journal.connection.execute('UPDATE retries SET attempts=99')
                journal.connection.commit()
                with self.assertRaises(ValueError):
                    journal.retries()
