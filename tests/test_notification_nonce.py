import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from discord.http import handle_message_parameters
from snake_media.bot import SnakeMediaClient
from snake_media.delivery_journal import DeliveryJournal
from snake_media.notifications import NotificationDelivery
from snake_media.service import RequestService
from test_core import config

ROW = {'notificationKey': 'completion:original', 'destinationId': '333',
       'payload': {'userId': '111', 'messageId': '444', 'text': 'Ready'}}


class ProcessStopped(BaseException):
    pass


class NotificationNonceTests(unittest.IsolatedAsyncioTestCase):
    async def test_restart_after_discord_acceptance_recovers_original_message(self):
        accepted = {}
        calls = []

        async def send(channel, message, text, **options):
            nonce = options.get('nonce')
            self.assertIsNotNone(nonce)
            calls.append(nonce)
            if nonce not in accepted:
                accepted[nonce] = '555'
                # Discord has created the message, but the caller never saves it.
                raise ProcessStopped()
            return accepted[nonce]

        transport = SimpleNamespace(poll=AsyncMock(return_value=[ROW]), acknowledge=AsyncMock())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'delivery.sqlite3'
            with DeliveryJournal(path) as journal:
                with self.assertRaises(ProcessStopped):
                    await NotificationDelivery(transport, send, {'111'}, {'333'}, journal).tick()
                self.assertIsNone(journal.get(ROW['notificationKey']))
            transport.acknowledge.assert_not_awaited()
            with DeliveryJournal(path) as journal:
                await NotificationDelivery(transport, send, {'111'}, {'333'}, journal).tick()
                self.assertEqual(journal.get(ROW['notificationKey']), '555')
        self.assertEqual(len(accepted), 1)
        self.assertEqual(calls[0], calls[1])
        transport.acknowledge.assert_awaited_once_with(ROW['notificationKey'], '555')

    async def test_distinct_notices_and_destinations_have_distinct_bounded_nonces(self):
        rows = [ROW, dict(ROW, notificationKey='completion:other'),
                dict(ROW, destinationId='334')]
        send = AsyncMock(return_value='555')
        for row in rows:
            transport = SimpleNamespace(poll=AsyncMock(return_value=[row]), acknowledge=AsyncMock())
            await NotificationDelivery(transport, send, {'111'}, {'333', '334'}).tick()
        nonces = [call.kwargs['nonce'] for call in send.await_args_list]
        self.assertEqual(len(set(nonces)), 3)
        for nonce in nonces:
            self.assertRegex(nonce, r'^[0-9a-f]{24}$')
            with handle_message_parameters(content='Ready', nonce=nonce) as parameters:
                self.assertEqual(parameters.payload['nonce'], nonce)
                self.assertIs(parameters.payload['enforce_nonce'], True)

    async def test_sender_forwards_nonce_and_preserves_reply(self):
        client = SnakeMediaClient(RequestService(config(), SimpleNamespace()))
        channel = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=555)))
        client.get_channel = lambda _: channel
        try:
            result = await client.send_notification('333', '444', 'Ready', nonce='a' * 24)
            self.assertEqual(result, '555')
            options = channel.send.call_args.kwargs
            self.assertEqual(options['nonce'], 'a' * 24)
            self.assertEqual(options['reference'].message_id, 444)
        finally:
            await client.close()
