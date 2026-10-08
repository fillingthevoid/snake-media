from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import discord
from snake_media.bot import SnakeMediaClient
from snake_media.card_registry import CardRegistry
from snake_media.n8n_client import format_result
from snake_media.service import RequestService
from test_core import config


class RelatedCardsTests(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_worker_recovers_after_a_state_failure(self):
        client = SnakeMediaClient(RequestService(config(), None))
        client.wait_until_ready = AsyncMock()
        client.cleanup_cards = AsyncMock(side_effect=[OSError('state unavailable'), None])
        with patch.object(client, 'is_closed', side_effect=[False, False, True]), patch('snake_media.bot.asyncio.sleep', new=AsyncMock()):
            await client.run_card_cleanup()
        self.assertEqual(client.cleanup_cards.await_count, 2)
        await client.close()

    async def test_accepted_action_queues_siblings_but_denied_action_keeps_them(self):
        with tempfile.TemporaryDirectory() as folder:
            with CardRegistry(Path(folder) / 'cards.sqlite3') as cards:
                for ident in ['100', '101']:
                    cards.remember('pending:13', '333', ident, '111')
                for accepted in [False, True]:
                    reply = format_result({'version': 1, 'status': 'notice', 'text': 'Handled', 'actionAccepted': accepted})
                    client = SnakeMediaClient(RequestService(config(), SimpleNamespace(action=AsyncMock(return_value=reply))), card_registry=cards)
                    interaction = SimpleNamespace(type=discord.InteractionType.component,
                        data={'custom_id': 'snake:13:confirm'}, user=SimpleNamespace(id=111), channel_id=333, guild_id=444,
                        response=SimpleNamespace(defer=AsyncMock()), followup=SimpleNamespace(send=AsyncMock()),
                        message=SimpleNamespace(id=101, embeds=[], components=[], edit=AsyncMock()), delete_original_response=AsyncMock())
                    interaction.edit_original_response=interaction.message.edit
                    await client.on_interaction(interaction)
                    self.assertEqual([r['message_id'] for r in cards.pending(now=0)], ['100'] if accepted else [])
                    await client.close()
