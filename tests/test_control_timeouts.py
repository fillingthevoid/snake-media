from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import discord
from snake_media.bot import SnakeMediaClient
from snake_media.service import RequestService
from test_core import config
from snake_media.card_registry import CardRegistry


class ControlTimeouts(unittest.TestCase):
    def test_deadline_survives_restart_and_removes_only_callbacks(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.sqlite3'
            with CardRegistry(path) as cards:
                cards.track('333', '100', '111', now=100,
                            links=[{'label': 'Watch', 'url': 'https://jellyfin.example.com'}],
                            webhook_id='999', webhook_token='private-token')
                cards.expire(399)
                self.assertEqual(cards.pending(399), [])
            with CardRegistry(path) as cards:
                self.assertTrue(cards.expired('333', '100', 400))
                cards.expire(400)
                job = cards.pending(400)[0]
                self.assertEqual(job['webhook_id'], '999')
                self.assertEqual(job['webhook_token'], 'private-token')
                cards.finish('333', '100')
                self.assertEqual(cards.pending(400), [])
                self.assertIsNone(cards.control('333', '100'))

    def test_only_owner_can_renew_and_expired_controls_cannot_be_revived(self):
        with tempfile.TemporaryDirectory() as folder:
            with CardRegistry(Path(folder) / 'state.sqlite3') as cards:
                cards.track('333', '100', '111', now=100)
                self.assertFalse(cards.touch('333', '100', '222', now=350))
                self.assertTrue(cards.touch('333', '100', '111', now=350))
                cards.expire(400)
                self.assertEqual(cards.pending(400), [])
                self.assertFalse(cards.touch('333', '100', '111', now=650))
                cards.expire(650)
                self.assertEqual(len(cards.pending(650)), 1)

    def test_private_component_renewal_tracks_its_original_response(self):
        with tempfile.TemporaryDirectory() as folder, CardRegistry(Path(folder) / 'state.sqlite3') as cards:
            cards.track('333', '100', '111', now=100, webhook_id='999', webhook_token='first-token')
            self.assertTrue(cards.touch('333', '100', '111', now=200, webhook_id='999', webhook_token='component-token'))
            row=cards.control('333', '100')
            self.assertEqual(row['webhook_token'], 'component-token')
            self.assertTrue(row['webhook_original'])


class CleanupTimeouts(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_does_not_strip_a_card_updated_during_fetch(self):
        with tempfile.TemporaryDirectory() as folder, CardRegistry(Path(folder) / 'state.sqlite3') as cards:
            client=SnakeMediaClient(RequestService(config(),SimpleNamespace()),card_registry=cards)
            client._connection.user=SimpleNamespace(id=999)
            message=SimpleNamespace(author=SimpleNamespace(id=999),components=[],edit=AsyncMock())
            async def fetch(_):
                cards.track('333','100','111')
                return message
            client.get_channel=lambda _:SimpleNamespace(fetch_message=fetch)
            cards.track('333','100','111',now=0)
            await client.cleanup_cards()
            message.edit.assert_not_awaited()
            self.assertFalse(cards.expired('333','100'))
            await client.close()

    async def test_private_expiry_uses_webhook_and_deletes_private_reference(self):
        with tempfile.TemporaryDirectory() as folder, CardRegistry(Path(folder) / 'state.sqlite3') as cards:
            client = SnakeMediaClient(RequestService(config(), SimpleNamespace()), card_registry=cards)
            cards.track('333', '100', '111', now=0, webhook_id='999', webhook_token='private-token')
            webhook = SimpleNamespace(edit_message=AsyncMock(), fetch_message=AsyncMock(return_value=SimpleNamespace(content='My requests')))
            client.fetch_channel = AsyncMock()
            with patch('snake_media.bot.discord.Webhook.partial', return_value=webhook):
                await client.cleanup_cards()
            webhook.edit_message.assert_awaited_once_with(100, view=None, content='My requests\n\nMenu expired. Use /help or /status to reopen.')
            client.fetch_channel.assert_not_awaited()
            self.assertIsNone(cards.control('333', '100'))
            await client.close()

    async def test_expired_press_never_reaches_backend(self):
        with tempfile.TemporaryDirectory() as folder, CardRegistry(Path(folder) / 'state.sqlite3') as cards:
            backend = SimpleNamespace(action=AsyncMock())
            client = SnakeMediaClient(RequestService(config(), backend), card_registry=cards)
            client.cleanup_cards = AsyncMock()
            cards.track('333', '100', '111', now=0)
            i = SimpleNamespace(type=discord.InteractionType.component, data={'custom_id':'snake:12:notice_7'},
                user=SimpleNamespace(id=111), channel_id=333, guild_id=444,
                message=SimpleNamespace(id=100), response=SimpleNamespace(send_message=AsyncMock()))
            await client.on_interaction(i)
            backend.action.assert_not_awaited()
            self.assertIn('timed out', i.response.send_message.call_args.args[0])
            await client.close()

    async def test_elapsed_public_buttons_are_removed_and_watch_link_remains(self):
        with tempfile.TemporaryDirectory() as folder:
            with CardRegistry(Path(folder) / 'state.sqlite3') as cards:
                client = SnakeMediaClient(RequestService(config(), SimpleNamespace()), card_registry=cards)
                client._connection.user = SimpleNamespace(id=999)
                watch = SimpleNamespace(url='https://jellyfin.example.com', label='Watch', custom_id=None)
                choice = SimpleNamespace(url=None, custom_id='snake:12:notice_7')
                message = SimpleNamespace(author=SimpleNamespace(id=999), components=[SimpleNamespace(children=[choice, watch])], edit=AsyncMock())
                client.get_channel = lambda _: SimpleNamespace(fetch_message=AsyncMock(return_value=message))
                cards.track('333', '100', '111', now=0)
                await client.cleanup_cards()
                self.assertEqual([b.label for b in message.edit.call_args.kwargs['view'].children], ['Watch'])
                self.assertEqual(cards.pending(1000), [])
                await client.close()
