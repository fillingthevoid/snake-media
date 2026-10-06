import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
from snake_media.bot import SnakeMediaClient
from snake_media.n8n_client import format_result
from snake_media.service import RequestService
from test_core import config


class ExpiryFeedbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_expiry_preview_edits_card_and_always_acknowledges_choice(self):
        reply=format_result({'version':1,'status':'confirmation','text':'Selected: extend 7 days. Confirm to save.',
            'pendingId':'13','choices':[{'label':'Confirm','action':'confirm'}],'actionAccepted':True})
        backend=SimpleNamespace(action=AsyncMock(return_value=reply))
        client=SnakeMediaClient(RequestService(config(),backend))
        i=SimpleNamespace(type=discord.InteractionType.component,data={'custom_id':'snake:12:notice_7'},
            user=SimpleNamespace(id=111),channel_id=333,guild_id=444,
            response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()),
            message=SimpleNamespace(embeds=[],components=[],edit=AsyncMock()),delete_original_response=AsyncMock())
        await client.on_interaction(i)
        self.assertEqual(i.message.edit.await_args.kwargs['view'].children[0].custom_id,'snake:13:confirm')
        i.followup.send.assert_awaited_once()
        self.assertTrue(i.followup.send.await_args.kwargs['ephemeral'])
        self.assertEqual(i.followup.send.await_args.kwargs['content'],str(reply))
        self.assertNotIn('view',i.followup.send.await_args.kwargs)
        backend.action.assert_awaited_once()
        await client.close()

    async def test_terminal_edit_preserves_link_and_reports_saved_change(self):
        from snake_media.confirmations import edit_presentation
        reply=format_result({'version':1,'status':'notice','text':'Kept permanently.','actionAccepted':True,'retentionUpdated':True})
        rows=[SimpleNamespace(children=[SimpleNamespace(url='https://jellyfin.example.com/web/index.html#!/details?id=abc',label='Open in Jellyfin'),SimpleNamespace(url=None,label='Keep permanently')])]
        options=edit_presentation(reply,[],rows)
        self.assertEqual([b.label for b in options['view'].children],['Open in Jellyfin'])
        self.assertIsNone(options['view'].children[0].custom_id)
        backend=SimpleNamespace(action=AsyncMock(return_value=reply));client=SnakeMediaClient(RequestService(config(),backend))
        i=SimpleNamespace(type=discord.InteractionType.component,data={'custom_id':'snake:13:confirm'},
            user=SimpleNamespace(id=111),channel_id=333,guild_id=444,
            response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()),
            message=SimpleNamespace(embeds=[],components=rows,edit=AsyncMock()),delete_original_response=AsyncMock())
        await client.on_interaction(i)
        i.followup.send.assert_awaited_once()
        self.assertIn('Kept permanently',i.followup.send.await_args.kwargs['content'])
        await client.close()
