import importlib.util,json,unittest
from pathlib import Path
from snake_media.confirmations import CUSTOM_ID,presentation
from snake_media.n8n_client import format_result
class RequestCardSimplificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_actions_round_trip_through_discord_validation(self):
        for action in ['mr_details','mr_summary','mr_extend_7','mr_extend_30']:
            reply=format_result({'version':1,'status':'confirmation','text':'Example','pendingId':'12','choices':[{'label':'Choice','action':action}]})
            custom=presentation(reply)['view'].children[0].custom_id
            self.assertEqual(CUSTOM_ID.fullmatch(custom).group(2),action)
    async def test_scoped_overlay_is_idempotent_and_keeps_private_suffixes(self):
        spec=importlib.util.spec_from_file_location('cards',Path('n8n/my-requests-simplification/patch.py'))
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        source=json.loads(Path('config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        out=m.build(source);self.assertEqual(out,source)
        for w in out:
            self.assertEqual(w['connections'],next(x for x in source if x['id']==w['id'])['connections'])
        status=next(w for w in out if w['id']=='snakeStatusInspectV1')
        code=next(n for n in status['nodes'] if n['name']=='Describe Status')['parameters']['jsCode']
        self.assertIn('jellyfinLinks(',code);self.assertIn('projection.summaryText',code)
