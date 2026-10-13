import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ReviewOverlayTests(unittest.TestCase):
    def test_authentication_storage_and_unrelated_workflows(self):
        spec=importlib.util.spec_from_file_location('reviews',ROOT/'n8n/media-reviews/patch.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        old=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        env={'ALLOWED_DISCORD_USER_IDS':'10,11','ADMIN_DISCORD_USER_IDS':'10','ALLOWED_DISCORD_CHANNEL_IDS':'30'}
        new=module.build(old,env);self.assertEqual(new,module.build(new,env))
        w=next(w for w in new if w['id']=='snakeMediaReviewsV1');nodes={n['name']:n for n in w['nodes']}
        original=next(n for w in old if w['id']=='HXtTzVTrpNZMZVt3' for n in w['nodes'] if n['name']=='Discord Webhook')
        self.assertEqual(nodes['Review Webhook']['credentials'],original['credentials'])
        self.assertEqual(nodes['Review Webhook']['parameters']['authentication'],'headerAuth')
        self.assertEqual(nodes['Save Review Row']['parameters']['operation'],'upsert')
        self.assertEqual({f['keyName'] for f in nodes['Save Review Row']['parameters']['filters']['conditions']},{'source','state','requestKey'})
        self.assertNotIn('mutex',json.dumps(w).lower())
        for before,after in zip(old,new):
            if before['id']!='snakeMediaReviewsV1' and not any('// Shared n8n expiry policy' in n.get('parameters',{}).get('jsCode','') for n in before['nodes']):self.assertEqual(before,after)
