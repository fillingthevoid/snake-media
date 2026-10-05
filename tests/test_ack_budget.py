import asyncio
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from snake_media.delivery_journal import DeliveryJournal
from snake_media.notifications import NotificationDelivery

ROW = {'notificationKey': 'new', 'destinationId': '333',
       'payload': {'userId': '111', 'messageId': '444', 'text': 'Ready'}}


class AcknowledgementBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_backlog_retries_are_capped_and_rotate_before_new_delivery(self):
        with tempfile.TemporaryDirectory() as folder:
            with DeliveryJournal(Path(folder) / 'state.sqlite3') as journal:
                for i in range(12):
                    journal.record('old:' + str(i), str(500 + i))
                async def ack(key, message):
                    if key != 'new':
                        raise OSError('offline')
                transport = SimpleNamespace(poll=AsyncMock(return_value=[ROW]), acknowledge=AsyncMock(side_effect=ack))
                send = AsyncMock(return_value='600')
                worker = NotificationDelivery(transport, send, {'111'}, {'333'}, journal)
                with self.assertLogs('snake_media', level='WARNING'):
                    await worker.tick()
                self.assertEqual([c.args[0] for c in transport.acknowledge.await_args_list], ['old:0', 'old:1', 'old:2', 'old:3', 'old:4', 'new'])
                send.assert_awaited_once()
                self.assertEqual(len(journal.pending()), 12)
                self.assertEqual(list(transport.poll.call_args.kwargs['exclude'])[:5], ['old:0', 'old:1', 'old:2', 'old:3', 'old:4'])
                transport.acknowledge.reset_mock()
                transport.poll.return_value = []
                with self.assertLogs('snake_media', level='WARNING'):
                    await worker.tick()
                self.assertEqual([c.args[0] for c in transport.acknowledge.await_args_list], ['old:5', 'old:6', 'old:7', 'old:8', 'old:9'])

    async def test_time_budget_stops_old_work_and_hung_initial_ack_does_not_resend(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.sqlite3'
            now = [0]
            async def ack(key, message):
                if key == 'new':
                    await asyncio.Event().wait()
                now[0] += 3
                raise OSError('offline')
            transport = SimpleNamespace(poll=AsyncMock(return_value=[ROW]), acknowledge=AsyncMock(side_effect=ack))
            send = AsyncMock(return_value='600')
            with DeliveryJournal(path) as journal:
                for i in range(8):
                    journal.record('old:' + str(i), str(500 + i))
                worker = NotificationDelivery(transport, send, {'111'}, {'333'}, journal, clock=lambda: now[0])
                with patch('snake_media.notifications.ACK_TIMEOUT_SECONDS', 0.01):
                    with self.assertLogs('snake_media', level='WARNING'):
                        await asyncio.wait_for(worker.tick(), timeout=0.3)
                self.assertEqual([c.args[0] for c in transport.acknowledge.await_args_list], ['old:0', 'old:1', 'new'])
                self.assertEqual(journal.pending()['new'], '600')
            with DeliveryJournal(path) as journal:
                transport.acknowledge = AsyncMock()
                worker = NotificationDelivery(transport, send, {'111'}, {'333'}, journal)
                await worker.tick()
                send.assert_awaited_once()

    async def test_hung_old_ack_is_cancelled_and_small_queue_is_tried_once_per_cycle(self):
        transport = SimpleNamespace(poll=AsyncMock(return_value=[]), acknowledge=AsyncMock(side_effect=lambda *args: None))
        worker = NotificationDelivery(transport, AsyncMock(), {'111'}, {'333'})
        worker.pending_acks['old'] = '555'
        async def hung(*args):
            await asyncio.Event().wait()
        transport.acknowledge.side_effect = hung
        with patch('snake_media.notifications.ACK_TIMEOUT_SECONDS', 0.01):
            with self.assertLogs('snake_media', level='WARNING'):
                await asyncio.wait_for(worker.tick(), timeout=0.3)
        transport.acknowledge.assert_awaited_once()
        transport.poll.assert_awaited_once()
        self.assertEqual(worker.pending_acks, {'old': '555'})
