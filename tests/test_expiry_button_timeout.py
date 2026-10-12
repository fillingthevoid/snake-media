from pathlib import Path
import tempfile
import unittest
from snake_media.card_registry import CardRegistry

class ExpiryButtonTimeoutTests(unittest.TestCase):
    def test_six_hour_deadline_survives_restart_and_does_not_renew(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'cards.sqlite3'
            with CardRegistry(path) as c:
                c.track('333','100','111',now=100,lifetime=21600)
                c.track('333','101','111',now=100)
            with CardRegistry(path) as c:
                self.assertFalse(c.expired('333','100',now=21699))
                self.assertTrue(c.expired('333','101',now=400))
                self.assertFalse(c.touch('333','100','222',now=1000))
                self.assertTrue(c.touch('333','100','111',now=1000))
                self.assertEqual(c.control('333','100')['expires_at'],21700)
                c.expire(21699)
                self.assertNotIn('100',[j['message_id'] for j in c.pending(21699)])
                c.expire(21700)
                self.assertIn('100',[j['message_id'] for j in c.pending(21700)])

from unittest.mock import Mock, patch
from snake_media.bot import SnakeMediaClient
from snake_media.confirmations import notification_view
import discord
class ExpiryTrackingTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_notice_buttons_get_the_long_deadline(self):
        bot=Mock();bot.card_registry=Mock()
        message=Mock(id=100)
        SnakeMediaClient.track_controls(bot,message,'111','333',notification_view('12'))
        self.assertEqual(bot.card_registry.track.call_args.kwargs['lifetime'],21600)
        view=discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label='Confirm',custom_id='snake:12:confirm'))
        SnakeMediaClient.track_controls(bot,message,'111','333',view)
        self.assertEqual(bot.card_registry.track.call_args.kwargs['lifetime'],300)
