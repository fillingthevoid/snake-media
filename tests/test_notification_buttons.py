import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from snake_media.notifications import NotificationDelivery
from snake_media.bot import SnakeMediaClient
from snake_media.service import RequestService
from snake_media.n8n_client import format_result
from test_core import config
import discord

class NoticeButtonTests(unittest.IsolatedAsyncioTestCase):
    async def test_delivery_passes_durable_notice_id_and_renders_three_controls(self):
        transport=SimpleNamespace(poll=AsyncMock(return_value=[{'id':'12','notificationKey':'k','destinationId':'333','payload':{'userId':'111','messageId':'444','text':'Ready'}}]),acknowledge=AsyncMock())
        send=AsyncMock(return_value='555')
        await NotificationDelivery(transport,send,{'111'},{'333'}).tick()
        send.assert_awaited_once_with('333','444','Ready',notice_id='12')
        client=SnakeMediaClient(RequestService(config(),SimpleNamespace()))
        channel=SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=555)))
        client.get_channel=lambda _:channel
        await client.send_notification('333','444','Ready',notice_id='12')
        view=channel.send.call_args.kwargs['view']
        self.assertEqual([b.label for b in view.children],['Extend 7 days','Extend 30 days','Keep permanently'])
        self.assertEqual([b.custom_id for b in view.children],['snake:12:notice_7','snake:12:notice_30','snake:12:notice_keep'])
        await client.close()

    async def test_notice_click_opens_private_confirmation_without_editing_success(self):
        reply=format_result({'version':1,'status':'confirmation','text':'Extend?', 'pendingId':'99','choices':[{'label':'Confirm','action':'confirm'}]})
        backend=SimpleNamespace(action=AsyncMock(return_value=reply))
        client=SnakeMediaClient(RequestService(config(),backend))
        i=SimpleNamespace(type=discord.InteractionType.component,data={'custom_id':'snake:12:notice_30'},user=SimpleNamespace(id=111),channel_id=333,guild_id=444,response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()),message=SimpleNamespace(edit=AsyncMock()))
        await client.on_interaction(i)
        backend.action.assert_awaited_once_with('111','333','444','12','notice_30')
        i.message.edit.assert_not_awaited()
        self.assertTrue(i.followup.send.call_args.kwargs['ephemeral'])
        self.assertEqual(i.followup.send.call_args.kwargs['view'].children[0].custom_id,'snake:99:confirm')
        await client.close()
