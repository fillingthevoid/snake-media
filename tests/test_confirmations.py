import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from snake_media.n8n_client import format_result, N8NError
from snake_media.service import RequestService
from test_core import config

class ConfirmationTests(unittest.IsolatedAsyncioTestCase):
    async def test_terminal_reply_can_be_sent_as_discord_followup(self):
        import aiohttp
        import discord
        from discord.webhook.async_ import async_context
        from snake_media.confirmations import presentation

        # Exercise discord.py validation and serialization; replace only delivery.
        adapter = SimpleNamespace(execute_webhook=AsyncMock(return_value={}))
        context_token = async_context.set(adapter)
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook(
                    {'id': '123', 'type': 3, 'token': 'test-only'}, session)
                for text in ('Search started for 41 aired episodes.', 'Cancelled',
                             'Could not process this request right now.'):
                    with self.subTest(text=text), patch.object(
                        discord.Webhook, '_create_message', return_value=SimpleNamespace(id=456)
                    ):
                        reply = format_result({'version': 1, 'status': 'notice', 'text': text})
                        await webhook.send(ephemeral=True, **presentation(reply))
                        payload = adapter.execute_webhook.call_args.kwargs['payload']
                        self.assertEqual(payload['content'], text)
                        self.assertEqual(payload['flags'], 64)
                        self.assertEqual(payload['allowed_mentions']['parse'], [])
        finally:
            async_context.reset(context_token)

    async def test_preview_preserves_controls_and_safe_poster(self):
        reply=format_result({'version':1,'status':'confirmation','text':'The Matrix (1999)\nIs this correct?',
            'posterUrl':'https://image.tmdb.org/t/p/w500/x.jpg','pendingId':'12',
            'choices':[{'label':'Confirm','action':'confirm'},{'label':'Cancel','action':'cancel'}]})
        self.assertEqual(reply.pending_id,'12')
        self.assertEqual(reply.choices[0]['action'],'confirm')
        self.assertIn('image.tmdb.org',reply.poster_url)
        with self.assertRaises(N8NError):
            format_result({'version':1,'status':'confirmation','text':'X','pendingId':'12','choices':[{'label':'Bad','action':'https://evil'}]})

    async def test_callbacks_reauthorize_before_forwarding(self):
        backend=SimpleNamespace(action=AsyncMock(return_value='ok'))
        service=RequestService(config(),backend)
        self.assertTrue(hasattr(service,'handle_action'))
        denied=await service.handle_action('999','333','444','12','confirm')
        self.assertIn('authorized',denied)
        backend.action.assert_not_awaited()
        await service.handle_action('111','555','444','12','confirm')
        backend.action.assert_not_awaited()
        self.assertEqual(await service.handle_action('111','333','444','12','confirm'),'ok')
        backend.action.assert_awaited_once()

    async def test_gateway_button_is_acknowledged_before_backend_and_uses_ephemeral_reply(self):
        import discord
        from snake_media.bot import SnakeMediaClient
        backend=SimpleNamespace(action=AsyncMock(return_value=format_result({'version':1,'status':'notice','text':'Cancelled'})))
        client=SnakeMediaClient(RequestService(config(),backend))
        interaction=SimpleNamespace(type=discord.InteractionType.component,
            data={'custom_id':'snake:12:cancel'},user=SimpleNamespace(id=111),channel_id=333,guild_id=444,
            response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
        await client.on_interaction(interaction)
        interaction.response.defer.assert_awaited_once_with(ephemeral=True,thinking=True)
        backend.action.assert_awaited_once_with('111','333','444','12','cancel')
        self.assertTrue(interaction.followup.send.call_args.kwargs['ephemeral'])
        await client.close()

    async def test_accepted_action_edits_original_preserving_poster_and_removes_controls(self):
        import discord
        from snake_media.bot import SnakeMediaClient
        reply=format_result({'version':1,'status':'notice','text':'Cancelled','actionAccepted':True})
        backend=SimpleNamespace(action=AsyncMock(return_value=reply))
        client=SnakeMediaClient(RequestService(config(),backend))
        poster=discord.Embed(description='Is this correct?');poster.set_image(url='https://image.tmdb.org/t/p/w500/x.jpg')
        interaction=SimpleNamespace(type=discord.InteractionType.component,
            data={'custom_id':'snake:12:cancel'},user=SimpleNamespace(id=111),channel_id=333,guild_id=444,
            response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()),
            message=SimpleNamespace(embeds=[poster],edit=AsyncMock()),delete_original_response=AsyncMock())
        await client.on_interaction(interaction)
        options=interaction.message.edit.call_args.kwargs
        self.assertIsNone(options['view'])
        self.assertEqual(options['embed'].description,'Cancelled')
        self.assertEqual(options['embed'].image.url,poster.image.url)
        self.assertEqual(poster.description,'Is this correct?')
        interaction.delete_original_response.assert_awaited_once()
        interaction.followup.send.assert_not_awaited()
        await client.close()

    async def test_accepted_next_choice_replaces_controls_and_edit_failure_falls_back(self):
        from snake_media.confirmations import edit_presentation
        reply=format_result({'version':1,'status':'confirmation','text':'Choose season','pendingId':'12',
            'choices':[{'label':'Latest','action':'latest'}],'actionAccepted':True})
        options=edit_presentation(reply,[])
        self.assertEqual([b.custom_id for b in options['view'].children],['snake:12:latest'])
        self.assertTrue(reply.action_accepted)
        self.assertFalse(getattr(format_result({'version':1,'status':'notice','text':'Denied','actionAccepted':'true'}),'action_accepted',False))

    async def test_card_edit_failure_returns_result_without_replaying_backend(self):
        import discord
        from snake_media.bot import SnakeMediaClient
        reply=format_result({'version':1,'status':'notice','text':'Cancelled','actionAccepted':True})
        backend=SimpleNamespace(action=AsyncMock(return_value=reply))
        client=SnakeMediaClient(RequestService(config(),backend))
        failure=discord.NotFound(SimpleNamespace(status=404,reason='Not Found'), 'message removed')
        interaction=SimpleNamespace(type=discord.InteractionType.component,
            data={'custom_id':'snake:12:cancel'},user=SimpleNamespace(id=111),channel_id=333,guild_id=444,
            response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()),
            message=SimpleNamespace(embeds=[],edit=AsyncMock(side_effect=failure)),delete_original_response=AsyncMock())
        with self.assertLogs('snake_media',level='WARNING'):
            await client.on_interaction(interaction)
        backend.action.assert_awaited_once()
        interaction.followup.send.assert_awaited_once()
        self.assertEqual(interaction.followup.send.call_args.kwargs['content'],'Cancelled')
        interaction.delete_original_response.assert_not_awaited()
        await client.close()
