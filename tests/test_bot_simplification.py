import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock

import discord
from snake_media.card_registry import CardRegistry
from snake_media.n8n_client import format_result
from test_request_commands import client, interaction


class SimplificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_details_edits_original_and_other_owner_never_reaches_backend(self):
        with tempfile.TemporaryDirectory() as d, CardRegistry(Path(d)/'cards.sqlite3') as cards:
            bot, backend=client();bot.card_registry=cards
            i, message=interaction();i.type=discord.InteractionType.component;i.message=message
            i.application_id=999;i.token='test-token';i.edit_original_response=AsyncMock(return_value=message)
            i.response.send_message=AsyncMock()
            cards.track('333',str(message.id),'999')
            try:
                await bot.menu_command(i,'serverdetails')
                backend.submit.assert_not_awaited();i.edit_original_response.assert_not_awaited()
                cards.connection.execute('DELETE FROM controls');cards.connection.commit()
                cards.track('333',str(message.id),'111')
                backend.submit.return_value=format_result({'version':1,'status':'notice','text':'Technical readings',
                    'menuChoices':[{'label':'Back','action':'serverstatus'}]})
                await bot.menu_command(i,'serverdetails')
                self.assertEqual(backend.submit.await_args.args[0].text,'serverdetails')
                self.assertEqual(i.edit_original_response.await_args.kwargs['content'],'Technical readings')
                i.followup.send.assert_not_awaited()
            finally:await bot.close()

    async def test_overlay_preserves_private_links_and_native_connections(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('simplification',root/'n8n/bot-simplification/patch.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        rows=json.loads((root/'config-templates/n8n-current-media-workflows.json').read_text())
        self.assertEqual(m.build(rows),rows)
        policy=(root/'n8n/polish/presentation/policy.js').read_text(encoding='utf-8-sig')
        code=policy.replace("const LOCAL_JELLYFIN_BASE='';","const LOCAL_JELLYFIN_BASE='http://10.1.2.3:8096';").replace('http://192.168.1.10:8096','https://remote.example.com')+'\nreturn [{json:feedback($json)}];'
        changed=m.replace_policy(code,policy)
        self.assertIn('http://10.1.2.3:8096',changed)
        self.assertIn('https://remote.example.com',changed)
        self.assertTrue(changed.endswith('return [{json:feedback($json)}];'))
