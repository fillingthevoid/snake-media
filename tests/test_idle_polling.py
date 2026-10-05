import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from snake_media.notifications import NotificationDelivery


class IdlePollingTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_polls_back_off_but_errors_and_pending_work_stay_active(self):
        transport=SimpleNamespace(poll=AsyncMock(return_value=[]),acknowledge=AsyncMock())
        worker=NotificationDelivery(transport,AsyncMock(),{'111'},{'333'})
        self.assertTrue(await worker.tick())
        self.assertEqual([worker.poll_interval(True) for _ in range(4)], [60,120,180,180])
        worker.pending_acks['k']='555'
        transport.acknowledge.side_effect=OSError('offline')
        with self.assertLogs('snake_media',level='WARNING'):
            self.assertFalse(await worker.tick())
        self.assertEqual(worker.poll_interval(False),60)
        worker.pending_acks.clear()
        transport.poll.side_effect=OSError('offline')
        with self.assertLogs('snake_media',level='WARNING'):
            self.assertFalse(await worker.tick())

    async def test_wake_during_poll_is_not_lost_and_interrupts_idle_wait(self):
        transport=SimpleNamespace(poll=AsyncMock(return_value=[]),acknowledge=AsyncMock())
        worker=NotificationDelivery(transport,AsyncMock(),{'111'},{'333'})
        worker.poll_interval(True);worker.poll_interval(True)
        worker.wake()
        self.assertEqual(worker.empty_polls,0)
        await asyncio.wait_for(worker.wait_for_work(180),timeout=0.1)
        worker.wake_event.clear()
        waiting=asyncio.create_task(worker.wait_for_work(180))
        await asyncio.sleep(0)
        worker.wake()
        await asyncio.wait_for(waiting,timeout=0.1)

    async def test_run_clears_old_wake_before_poll_and_preserves_a_new_wake(self):
        transport=SimpleNamespace(acknowledge=AsyncMock())
        worker=NotificationDelivery(transport,AsyncMock(),{'111'},{'333'})
        self.assertTrue(hasattr(worker,'wake_event'))
        closed=[False]
        async def poll(**kwargs):worker.wake();return []
        transport.poll=poll
        delays=[]
        async def wait(delay):
            delays.append(delay)
            self.assertTrue(worker.wake_event.is_set())
            closed[0]=True
        worker.wait_for_work=wait
        client=SimpleNamespace(is_closed=lambda:closed[0],wait_until_ready=AsyncMock())
        await worker.run(client)
        self.assertEqual(delays,[60])
