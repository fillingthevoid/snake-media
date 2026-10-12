import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class HelpDefaultsOverlay(unittest.TestCase):
    def test_owned_storage_is_after_claim_and_keeps_other_workflows_and_bindings(self):
        spec=importlib.util.spec_from_file_location('defaults',ROOT/'n8n/help-defaults/patch.py')
        p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
        old=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        new=p.build(old);self.assertEqual(new,p.build(new))
        before={w['id']:w for w in old};after={w['id']:w for w in new}
        for wid,w in before.items():
            nodes={n['name']:n for n in after[wid]['nodes']}
            for n in w['nodes']:
                self.assertEqual(n.get('credentials'),nodes[n['name']].get('credentials'))
                if n['type'].endswith('.httpRequest') or n['name'].startswith(('Claim ','Save ','Authorized ')):
                    self.assertEqual(n,nodes[n['name']])
            if wid not in p.IDS:self.assertEqual(w,after[wid])
        w=after['snakeRecommendV1'];nodes={n['name']:n for n in w['nodes']}
        for name in ['Read Recommendation Settings','Store Recommendation Settings']:
            n=nodes[name];keys={f['keyName'] for f in n['parameters']['filters']['conditions']}
            self.assertEqual(keys,{'source','userId','state','requestKey'})
            self.assertEqual(n['onError'],'continueRegularOutput')
        self.assertEqual(nodes['Store Recommendation Settings']['parameters']['operation'],'upsert')
        self.assertEqual(w['connections']['Generate Recommendations?']['main'][0][0]['node'],'Prepare Recommendation Setting')
        self.assertEqual(w['connections']['Recommendation Claimed?']['main'][0][0]['node'],'Recommendation Selected?')
        self.assertEqual(w['connections']['Restore Recommendation Generation']['main'][0][0]['node'],'Recommendation Generation Context')
        self.assertIn('more',next(n for n in after['snakeTelegramCardV1']['nodes'] if n['name']=='Shared Menu Data')['parameters']['jsCode'])
