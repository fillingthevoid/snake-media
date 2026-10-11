import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
from snake_media.notifications import NotificationDelivery, NotificationTransport
from snake_media.delivery_journal import DeliveryJournal
from snake_media.n8n_client import format_result
from test_request_commands import client, interaction


class RestoreReconciliationTests(unittest.IsolatedAsyncioTestCase):
    async def test_slash_preview_retries_as_text_with_same_controls_when_embeds_are_denied(self):
        c, backend = client()
        i, card = interaction()
        reply = format_result({'version': 1, 'status': 'confirmation', 'text': '*' * 1800,
            'pendingId': '1', 'posterUrl': 'https://image.tmdb.org/t/p/w500/x.jpg',
            'choices': [{'label': 'Confirm', 'action': 'confirm'}]})
        backend.submit.return_value = reply
        card.edit.side_effect = [discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'Embed denied'), None]
        try:
            await c.request_command(i, 'Example')
            self.assertEqual(card.edit.await_count, 2)
            options = card.edit.call_args.kwargs
            self.assertIsNone(options['embed'])
            self.assertLessEqual(len(options['content'].encode('utf-16-le')) // 2, 2000)
            self.assertEqual(options['view'].children[0].custom_id, 'snake:1:confirm')
            self.assertFalse(options['allowed_mentions'].everyone)
            self.assertEqual(backend.submit.await_count, 1)
            self.assertEqual(i.followup.send.call_args.args[0], 'Your request: ' + card.jump_url)
        finally:
            await c.close()

    async def test_restored_pending_notice_is_reacknowledged_without_resending(self):
        for compact in (False, True):
            with self.subTest(compact=compact), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'journal.sqlite'
                key = 'discord:restored'
                row = {'notificationKey': key, 'destinationId': '333',
                       'payload': {'userId': '111', 'messageId': '444', 'text': 'Ready'}}
                with DeliveryJournal(path) as journal:
                    journal.record(key, '555')
                    journal.acknowledge(key)
                    if compact:
                        journal.compact(before=10**12)
                backend_pending = [row]
                bodies = []
                class Transport(NotificationTransport):
                    async def _post(self, body):
                        bodies.append(body)
                        if body['action'] == 'poll':
                            return {'notifications': backend_pending.copy(), 'version': 1}
                        backend_pending.clear()
                        return {'version': 1, 'acknowledged': True}
                send = AsyncMock()
                with DeliveryJournal(path) as journal:
                    delivery = NotificationDelivery(Transport('http://unused', 'test'), send, {'111'}, {'333'}, journal)
                    await delivery.tick()
                    await delivery.tick()
                self.assertEqual(backend_pending, [])
                send.assert_not_awaited()
                ack = next(b for b in bodies if b['action'] == 'ack')
                if compact:
                    self.assertIs(ack['receiptRecovered'], True)
                    self.assertNotIn('messageId', ack)
                else:
                    self.assertEqual(ack['messageId'], '555')

    async def test_failed_reconciliation_survives_restart_without_resending(self):
        key = 'discord:restored'
        row = {'notificationKey': key, 'destinationId': '333',
               'payload': {'userId': '111', 'messageId': '444', 'text': 'Ready'}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'journal.sqlite'
            with DeliveryJournal(path) as journal:
                journal.record(key, '555'); journal.acknowledge(key)
                journal.compact(before=10**12)
                transport = SimpleNamespace(poll=AsyncMock(return_value=[row]), acknowledge=AsyncMock(side_effect=OSError('offline')))
                send = AsyncMock()
                with self.assertLogs('snake_media', level='WARNING'):
                    await NotificationDelivery(transport, send, {'111'}, {'333'}, journal).tick()
            transport.acknowledge = AsyncMock()
            with DeliveryJournal(path) as journal:
                await NotificationDelivery(transport, send, {'111'}, {'333'}, journal).tick()
            transport.acknowledge.assert_awaited_once_with(key, None)
            send.assert_not_awaited()
