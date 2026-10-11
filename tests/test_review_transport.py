import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord

from snake_media.bot import SnakeMediaClient
from snake_media.config import Config
from snake_media.confirmations import presentation
from snake_media.n8n_client import format_result
from snake_media.service import RequestService


class ReviewTransportTests(unittest.IsolatedAsyncioTestCase):
    def client(self, reply='Preview'):
        config = Config.from_env({'DISCORD_TOKEN': 'test', 'ALLOWED_DISCORD_USER_IDS': '111',
                                  'ALLOWED_DISCORD_CHANNEL_IDS': '333'})
        backend = SimpleNamespace(submit=AsyncMock(return_value=reply))
        client = SnakeMediaClient(RequestService(config, backend))
        client._connection.user = SimpleNamespace(id=123)
        self.addAsyncCleanup(client.close)
        return client, backend

    def interaction(self, user=111):
        return SimpleNamespace(user=SimpleNamespace(id=user, name='test'), channel_id=333, guild_id=444,
                               id=876543210987654321, response=SimpleNamespace(defer=AsyncMock()),
                               followup=SimpleNamespace(send=AsyncMock()))

    async def test_title_free_extension_preserves_explicit_duration_at_backend(self):
        client, backend = self.client()
        await client.extend_command(self.interaction(), days=30)
        self.assertEqual(backend.submit.call_args.args[0].text, 'extend 30 days')
        await client.extend_command(self.interaction(), title='Example', days=14)
        self.assertEqual(backend.submit.call_args.args[0].text, 'extend Example 14 days')
        backend.submit.reset_mock()
        await client.extend_command(self.interaction(user=999), days=30)
        backend.submit.assert_not_awaited()

    async def test_oversized_escaped_confirmations_keep_all_text_and_controls(self):
        for text in ['*' * 1800, '😀' * 1200, '@everyone ' * 160]:
            with self.subTest(text=text[:10]):
                reply = format_result({'version': 1, 'status': 'confirmation', 'text': text,
                                       'pendingId': '1', 'choices': [{'label': 'Confirm', 'action': 'confirm'}]})
                options = presentation(reply)
                content = options['content']
                self.assertTrue(content is None or len(content.encode('utf-16-le')) // 2 <= 2000)
                if options['embed']:
                    self.assertEqual(options['embed'].description, str(reply))
                self.assertEqual(options['view'].children[0].custom_id, 'snake:1:confirm')
                self.assertFalse(options['allowed_mentions'].everyone)

    async def test_poster_free_message_and_notification_use_safe_presentation(self):
        reply = format_result({'version': 1, 'status': 'notice', 'text': '*' * 1800})
        client, _ = self.client(reply)
        sent = SimpleNamespace(id=987654321098765432)
        channel = SimpleNamespace(id=333, send=AsyncMock(return_value=sent))
        message = SimpleNamespace(content='<@123> Example', id=876543210987654321, webhook_id=None,
                                  author=SimpleNamespace(id=111, name='test', bot=False), channel=channel,
                                  guild=SimpleNamespace(id=444), reply=AsyncMock(return_value=sent))
        await client.on_message(message)
        self.assertIsNotNone(message.reply.call_args.kwargs.get('embed'))
        self.assertEqual(message.reply.call_args.kwargs['embed'].description, str(reply))
        client.get_channel = lambda identifier: channel
        await client.send_notification('333', '444', '*' * 1800, nonce='test')
        self.assertEqual(channel.send.call_args.kwargs['embed'].description, str(reply))
        self.assertIsNone(channel.send.call_args.kwargs['content'])

    async def test_missing_embed_permission_uses_bounded_escaped_text(self):
        reply = format_result({'version': 1, 'status': 'notice', 'text': '*' * 1800})
        client, _ = self.client(reply)
        response = SimpleNamespace(status=403, reason='Forbidden')
        message = SimpleNamespace(content='<@123> Example', id=876543210987654321, webhook_id=None,
                                  author=SimpleNamespace(id=111, name='test', bot=False),
                                  channel=SimpleNamespace(id=333), guild=SimpleNamespace(id=444),
                                  reply=AsyncMock(side_effect=[discord.Forbidden(response, 'Embed unavailable'), SimpleNamespace(id=987654321098765432)]))
        await client.on_message(message)
        self.assertEqual(message.reply.await_count, 2)
        options = message.reply.call_args.kwargs
        self.assertLessEqual(len(options['content'].encode('utf-16-le')) // 2, 2000)
        self.assertTrue(options['content'].endswith('…'))
        self.assertFalse(options['allowed_mentions'].everyone)

    async def test_notification_falls_back_when_embeds_are_denied(self):
        reply = format_result({'version': 1, 'status': 'notice', 'text': '*' * 1800})
        client, _ = self.client(reply)
        response = SimpleNamespace(status=403, reason='Forbidden')
        sent = SimpleNamespace(id=987654321098765432)
        channel = SimpleNamespace(send=AsyncMock(side_effect=[discord.Forbidden(response, 'Embed unavailable'), sent]))
        client.get_channel = lambda identifier: channel
        try:
            await client.send_notification('333', '444', '*' * 1800, nonce='durable')
        except discord.Forbidden:
            self.fail('Oversized notifications need a text fallback when embeds are denied')
        self.assertLessEqual(len(channel.send.call_args.kwargs['content']), 2000)
        self.assertEqual(channel.send.call_args.kwargs['nonce'], 'durable')

    async def test_slash_reply_falls_back_when_embeds_are_denied(self):
        reply = format_result({'version': 1, 'status': 'notice', 'text': '*' * 1800})
        client, _ = self.client(reply)
        response = SimpleNamespace(status=403, reason='Forbidden')
        sent = SimpleNamespace(id=987654321098765432)
        interaction = self.interaction()
        interaction.followup.send.side_effect = [discord.Forbidden(response, 'Embed unavailable'), sent]
        try:
            await client.read_command(interaction, 'status')
        except discord.Forbidden:
            self.fail('Oversized slash replies need a text fallback when embeds are denied')
        self.assertLessEqual(len(interaction.followup.send.call_args.kwargs['content']), 2000)
        self.assertTrue(interaction.followup.send.call_args.kwargs['ephemeral'])
