import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class MultipleSeasonsOverlay(unittest.TestCase):
    def test_overlay_preserves_bindings_and_is_idempotent(self):
        spec=importlib.util.spec_from_file_location('multi',ROOT/'n8n/multiple-seasons/patch.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        source=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        after=m.build(source);self.assertEqual(m.build(after),after)
        for a,b in zip(source,after):
            self.assertEqual(a['connections'],b['connections'])
            for old,new in zip(a['nodes'],b['nodes']):
                self.assertEqual(old.get('credentials'),new.get('credentials'))
                if old['type'].endswith('.httpRequest') or 'Authorized' in old['name']:
                    self.assertEqual(old,new)
        telegram=next(w for w in after if w['id']=='snakeTelegramCardV1')
        route=next(n for n in telegram['nodes'] if n['name']=='Recommendation Card?')
        self.assertIn('review$',route['parameters']['conditions']['conditions'][0]['leftValue'])
