import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from snake_media.bot import SnakeMediaClient
from snake_media.__main__ import serve
from snake_media.service import RequestService, TestBackend
from test_core import config


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_reply_disables_mentions_and_webhooks_are_ignored(self):
        client = SnakeMediaClient(RequestService(config(), TestBackend()))
        client._connection.user = SimpleNamespace(id=999)
        msg = SimpleNamespace(
            author=SimpleNamespace(id=111, name="test", bot=False),
            guild=SimpleNamespace(id=444), channel=SimpleNamespace(id=333),
            content="<@999> add Matrix", webhook_id=None, reply=AsyncMock(), id=888,
        )
        await client.on_message(msg)
        self.assertIn("No media request", msg.reply.call_args.args[0])
        self.assertFalse(msg.reply.call_args.kwargs["mention_author"])
        self.assertEqual(msg.reply.call_args.kwargs["allowed_mentions"].to_dict()["parse"], [])
        msg.reply.reset_mock()
        msg.webhook_id = 123
        await client.on_message(msg)
        msg.reply.assert_not_awaited()
        self.assertTrue(client.intents.guild_messages)
        self.assertFalse(client.intents.message_content)
        self.assertFalse(client.intents.members)
        await client.close()

    async def test_send_failure_does_not_escape_or_log_exception_content(self):
        client = SnakeMediaClient(RequestService(config(), TestBackend()))
        client._connection.user = SimpleNamespace(id=999)
        msg = SimpleNamespace(
            author=SimpleNamespace(id=111, name="test", bot=False),
            guild=SimpleNamespace(id=444), channel=SimpleNamespace(id=333),
            content="<@999> add Matrix", webhook_id=None,
            reply=AsyncMock(side_effect=RuntimeError("secret transport value")), id=888,
        )
        with self.assertLogs("snake_media", level="ERROR") as logs:
            await client.on_message(msg)
        self.assertNotIn("secret transport", " ".join(logs.output))
        await client.close()

    async def test_stop_cancels_gateway_and_closes_client(self):
        stopped = asyncio.Event()
        started = asyncio.Event()

        class Client:
            closed = False
            cancelled = False
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                self.closed = True
            async def start(self, token, *, reconnect):
                self.reconnect = reconnect
                started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    self.cancelled = True
                    raise

        client = Client()
        task = asyncio.create_task(serve(client, "test", stopped))
        await asyncio.wait_for(started.wait(), 1)
        stopped.set()
        await asyncio.wait_for(task, 1)
        self.assertTrue(client.closed)
        self.assertTrue(client.cancelled)
        self.assertTrue(client.reconnect)

    async def test_login_failure_is_propagated_for_nonzero_exit(self):
        class Client:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def start(self, token, *, reconnect):
                raise RuntimeError("login failed")
        with self.assertRaises(RuntimeError):
            await serve(Client(), "test", asyncio.Event())
