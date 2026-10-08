import unittest
from snake_media.command_menu import menu_text, menu_choices
from test_request_commands import client, interaction


class CommandMenu(unittest.TestCase):
    def test_help_is_short_and_details_are_separate(self):
        text = menu_text('help')
        self.assertLess(len(text), 350)
        for command in ['/request', '/recommend', '/status']:
            self.assertIn(command, text)
        self.assertNotIn('Watching', text)
        self.assertIn('30 days', menu_text('expiry'))
        self.assertIn('never extends', menu_text('expiry'))
        self.assertEqual([c['label'] for c in menu_choices('help')][:3],
                         ['Request', 'Recommend', 'My requests'])

    def test_unknown_navigation_is_rejected(self):
        with self.assertRaises(ValueError):
            menu_text('authorize')


class MenuNavigation(unittest.IsolatedAsyncioTestCase):
    async def test_help_buttons_are_short_and_denied_navigation_never_calls_backend(self):
        bot, backend = client()
        try:
            owner, _ = interaction()
            await bot.help_command(owner)
            buttons = owner.followup.send.call_args.kwargs['view'].children
            self.assertEqual([b.label for b in buttons][:3], ['Request', 'Recommend', 'My requests'])
            denied, _ = interaction(999)
            await bot.menu_command(denied, 'recommend')
            backend.submit.assert_not_awaited()
            await bot.menu_command(owner, 'status')
            self.assertEqual(backend.submit.call_args.args[0].text, 'status')
            self.assertEqual(backend.submit.call_args.args[0].user_id, '111')
        finally:
            await bot.close()
