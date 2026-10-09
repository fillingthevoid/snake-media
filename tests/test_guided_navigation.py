import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
from snake_media.bot import SnakeMediaClient
from snake_media.service import RequestService
from test_core import config

class GuidedNavigation(unittest.IsolatedAsyncioTestCase):
    async def test_request_menu_opens_modal_instead_of_instructions(self):
        client=SnakeMediaClient(RequestService(config(),SimpleNamespace()))
        client.service.command_allowed=lambda *a:True
        i=SimpleNamespace(user=SimpleNamespace(id=111),channel_id=333,guild_id=444,
                          response=SimpleNamespace(send_modal=AsyncMock(),defer=AsyncMock()))
        await client.menu_command(i,'request')
        i.response.send_modal.assert_awaited_once()
        self.assertIsInstance(i.response.send_modal.call_args.args[0],discord.ui.Modal)
        await client.close()

    async def test_unauthorized_actor_cannot_open_request_modal(self):
        client=SnakeMediaClient(RequestService(config(),SimpleNamespace()))
        client.service.command_allowed=lambda *a:False
        i=SimpleNamespace(user=SimpleNamespace(id=111),channel_id=333,guild_id=444,
                          response=SimpleNamespace(send_modal=AsyncMock(),send_message=AsyncMock()))
        await client.request_command(i)
        i.response.send_modal.assert_not_awaited()
        i.response.send_message.assert_awaited_once()
        await client.close()
