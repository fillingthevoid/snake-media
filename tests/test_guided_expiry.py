import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from snake_media.n8n_client import format_result, N8NError
from snake_media.confirmations import CUSTOM_ID, presentation
from snake_media.bot import SnakeMediaClient
from snake_media.service import RequestService
from test_core import config


class GuidedExpiryTests(unittest.IsolatedAsyncioTestCase):
    async def test_guided_actions_render_bounded_buttons_and_reject_invalid_actions(self):
        for action in ['rettitle_0', 'retpage_1', 'retdays_7', 'retdays_30']:
            reply=format_result({'version':1,'status':'confirmation','text':'Choose a title',
                'pendingId':'12','choices':[{'label':'Example','action':action}]})
            button=presentation(reply)['view'].children[0]
            self.assertEqual(button.custom_id,'snake:12:'+action)
            self.assertIsNotNone(CUSTOM_ID.fullmatch(button.custom_id))
        for action in ['rettitle_-1','retpage_1000','retdays_3650']:
            with self.assertRaises(N8NError):
                format_result({'version':1,'status':'confirmation','text':'Choose','pendingId':'12',
                    'choices':[{'label':'Bad','action':action}]})

    async def test_discord_expiry_commands_send_bare_or_full_command_to_backend(self):
        backend=SimpleNamespace(submit=AsyncMock(return_value='Choose a title'))
        client=SnakeMediaClient(RequestService(config(),backend))
        client._connection.user=SimpleNamespace(id=999)
        interaction=SimpleNamespace(id=123,user=SimpleNamespace(id=111,name='Example'),
            channel_id=333,guild_id=444,response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()))
        commands={c.name:c for c in client.tree.get_commands()}
        self.assertIn('extend',commands);self.assertIn('keep',commands)
        await client.extend_command(interaction)
        self.assertEqual(backend.submit.call_args.args[0].text,'extend')
        await client.extend_command(interaction,'Example',14)
        self.assertEqual(backend.submit.call_args.args[0].text,'extend Example 14 days')
        await client.keep_command(interaction,'Example')
        self.assertEqual(backend.submit.call_args.args[0].text,'keep Example permanently')
        await client.close()
