import unittest
from snake_media.confirmations import CUSTOM_ID, presentation
from snake_media.n8n_client import format_result, N8NError
from test_request_commands import client, interaction


class RecommendationCommands(unittest.IsolatedAsyncioTestCase):
    async def test_local_watch_links_accept_private_lan_addresses_and_reject_loopback(self):
        for address in ['10.23.4.5', '172.20.0.2', '192.168.50.50']:
            url='http://'+address+':8096/web/index.html#!/details?id=abc'
            self.assertEqual(format_result({'version':1,'status':'notice','text':'Available',
                'localJellyfinUrl':url}).local_jellyfin_url, url)
        for address in ['127.0.0.1', '169.254.0.2', '8.8.8.8', '0.0.0.0']:
            self.assertIsNone(format_result({'version':1,'status':'notice','text':'Available',
                'localJellyfinUrl':'http://'+address+':8096/web/index.html#!/details?id=abc'}).local_jellyfin_url)

    async def test_recommend_sends_owned_context_and_denied_user_never_reaches_backend(self):
        bot, backend = client()
        try:
            self.assertIsNotNone(bot.tree.get_command('recommend'))
            owner, _ = interaction()
            await bot.recommend_command(owner)
            request = backend.submit.call_args.args[0]
            self.assertEqual(request.text, 'recommend')
            self.assertEqual(request.user_id, '111')
            self.assertEqual(request.message_id, str(owner.id))
            self.assertTrue(request.requested_at.endswith('Z'))
            backend.submit.reset_mock()
            denied, _ = interaction(999)
            await bot.recommend_command(denied)
            backend.submit.assert_not_awaited()
        finally:
            await bot.close()

    async def test_recommendation_choices_keep_watch_links_and_reject_unbounded_actions(self):
        actions = ['rec_movie', 'rec_tv', 'rec_genre_0', 'rec_genre_16',
                   'rec_previous', 'rec_next', 'rec_choose', 'rec_cancel']
        reply = format_result({'version': 1, 'status': 'confirmation',
            'text': 'Available in Jellyfin.', 'pendingId': '12',
            'jellyfinUrl': 'https://media.example.com/web/index.html#!/details?id=abc',
            'choices': [{'label': action, 'action': action} for action in actions]})
        buttons = presentation(reply)['view'].children
        self.assertEqual(buttons[0].url, reply.jellyfin_url)
        self.assertEqual([b.custom_id for b in buttons[1:]], ['snake:12:'+a for a in actions])
        for action in actions:
            self.assertIsNotNone(CUSTOM_ID.fullmatch('snake:12:'+action))
        for action in ['rec_genre_17', 'rec_genre_99999', 'rec_delete', 'rec_choose_other']:
            self.assertIsNone(CUSTOM_ID.fullmatch('snake:12:'+action))
            with self.assertRaises(N8NError):
                format_result({'version': 1, 'status': 'confirmation', 'text': 'X',
                    'pendingId': '12', 'choices': [{'label': 'Bad', 'action': action}]})
