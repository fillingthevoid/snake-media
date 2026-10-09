import unittest
import discord
from snake_media.n8n_client import format_result, N8NError
from snake_media.confirmations import presentation, CUSTOM_ID

class RequestUsability(unittest.IsolatedAsyncioTestCase):
    async def test_empty_screen_renders_authorized_navigation_buttons(self):
        reply=format_result({'version':1,'status':'notice','text':'No requests yet.',
            'menuChoices':[{'label':'Request something','action':'request'},
                           {'label':'Get recommendations','action':'recommend'}]})
        buttons=presentation(reply)['view'].children
        self.assertEqual([b.custom_id for b in buttons],['snake_menu:request','snake_menu:recommend'])

    async def test_new_choices_pass_transport_and_persistent_dispatch(self):
        for action in ['wrong','back','match_7','retback','mr_filter_downloading','rec_back']:
            reply=format_result({'version':1,'status':'confirmation','text':'Choose.',
                'pendingId':'1','choices':[{'label':'Choose','action':action}]})
            self.assertEqual(presentation(reply)['view'].children[0].custom_id,'snake:1:'+action)
            self.assertIsNotNone(CUSTOM_ID.fullmatch('snake:1:'+action))

    async def test_backend_cannot_supply_an_admin_navigation_button(self):
        with self.assertRaises(N8NError):
            format_result({'version':1,'status':'notice','text':'No requests.',
                'menuChoices':[{'label':'Authorize','action':'authorize'}]})
