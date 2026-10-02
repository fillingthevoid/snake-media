import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from types import SimpleNamespace
from snake_media.notifications import NotificationDelivery
from snake_media.delivery_journal import DeliveryJournal

ROW={'notificationKey':'original','destinationId':'333','payload':{'userId':'111','messageId':'444','text':'Ready'}}

class JournalTests(unittest.IsolatedAsyncioTestCase):
    async def test_ack_failure_restart_retries_ack_without_resending(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'delivery.sqlite3'
            transport=SimpleNamespace(poll=AsyncMock(return_value=[ROW]),acknowledge=AsyncMock(side_effect=OSError('offline')))
            send=AsyncMock(return_value='555')
            with DeliveryJournal(path) as journal:
                first=NotificationDelivery(transport,send,{'111'},{'333'},journal=journal)
                with self.assertLogs('snake_media',level='WARNING'):await first.tick()
            transport.acknowledge=AsyncMock()
            with DeliveryJournal(path) as journal:
                second=NotificationDelivery(transport,send,{'111'},{'333'},journal=journal)
                await second.tick()
            send.assert_awaited_once()
            transport.acknowledge.assert_awaited_once_with('original','555')
            # Even a stale queue response after another restart must not resend.
            with DeliveryJournal(path) as journal:
                await NotificationDelivery(transport,send,{'111'},{'333'},journal=journal).tick()
            send.assert_awaited_once()

    async def test_receipt_conflicts_and_corrupt_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'delivery.sqlite3'
            with DeliveryJournal(path) as journal:
                journal.record('a','555')
                journal.record('a','555')
                with self.assertRaises(ValueError):journal.record('a','666')
                self.assertEqual(journal.pending(),{'a':'555'})
                journal.acknowledge('a')
                self.assertEqual(journal.pending(),{})
                self.assertEqual(journal.get('a'),'555')
            path.write_text('not a database')
            with self.assertRaises(Exception):DeliveryJournal(path)

    async def test_local_receipt_failure_retries_storage_before_ack_without_resending(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            transport=SimpleNamespace(poll=AsyncMock(return_value=[ROW]),acknowledge=AsyncMock())
            send=AsyncMock(return_value='555')
            with DeliveryJournal(Path(folder)/'delivery.sqlite3') as journal:
                delivery=NotificationDelivery(transport,send,{'111'},{'333'},journal=journal)
                with patch.object(journal,'record',side_effect=OSError('disk full')):
                    with self.assertLogs('snake_media',level='WARNING'):await delivery.tick()
                transport.acknowledge.assert_not_awaited()
                await delivery.tick()
                send.assert_awaited_once()
                transport.acknowledge.assert_awaited_once_with('original','555')
                self.assertEqual(journal.get('original'),'555')
