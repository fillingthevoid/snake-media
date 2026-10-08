import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
from snake_media.card_registry import CardRegistry
from test_request_commands import client


class ActiveCards(unittest.IsolatedAsyncioTestCase):
    async def test_owned_original_card_is_edited_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'cards.sqlite3'
            with CardRegistry(path) as registry:
                registry.remember_request('333','444','555','111')
            with CardRegistry(path) as registry:
                self.assertEqual(registry.request_card('333','444','111'),'555')
                self.assertIsNone(registry.request_card('333','444','222'))
                bot,_=client();bot.card_registry=registry
                card=SimpleNamespace(id=555,author=SimpleNamespace(id=123),embeds=[],edit=AsyncMock())
                channel=SimpleNamespace(fetch_message=AsyncMock(return_value=card),send=AsyncMock())
                bot.get_channel=lambda _:channel
                try:
                    result=await bot.send_notification('333','444','Available',notice_id='7',owner_id='111')
                    self.assertEqual(result,'555');card.edit.assert_awaited_once();channel.send.assert_not_awaited()
                    self.assertEqual(len(card.edit.call_args.kwargs['view'].children),3)
                finally:await bot.close()

    async def test_temporary_edit_failure_does_not_send_a_duplicate_or_acknowledge(self):
        with tempfile.TemporaryDirectory() as folder,CardRegistry(Path(folder)/'cards.sqlite3') as registry:
            registry.remember_request('333','444','555','111');bot,_=client();bot.card_registry=registry
            card=SimpleNamespace(id=555,author=SimpleNamespace(id=123),embeds=[],edit=AsyncMock(side_effect=TimeoutError()))
            channel=SimpleNamespace(fetch_message=AsyncMock(return_value=card),send=AsyncMock());bot.get_channel=lambda _:channel
            try:
                with self.assertRaises(TimeoutError):await bot.send_notification('333','444','Downloading',owner_id='111')
                channel.send.assert_not_awaited()
            finally:await bot.close()
