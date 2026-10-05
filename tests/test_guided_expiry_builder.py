import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class BuilderTests(unittest.TestCase):
    def test_overlay_keeps_bindings_and_claims_context_with_existing_atomic_claim(self):
        spec=importlib.util.spec_from_file_location('guide_build',ROOT/'n8n/guided-expiry/build.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        source=[json.loads(p.read_text(encoding='utf-8-sig')) for p in (ROOT/'n8n/retention-controls/workflows').glob('*.json')]
        result=module.build(source)
        old={w['id']:w for w in source}
        for w in result:
            original=old[w['id']]
            self.assertEqual(w['connections'],original['connections'])
            for n in w['nodes']:
                previous=next(x for x in original['nodes'] if x['name']==n['name'])
                self.assertEqual(n.get('credentials'),previous.get('credentials'))
                if n['name']=='Claim Choice':
                    self.assertEqual(n['parameters']['filters'],previous['parameters']['filters'])
                    self.assertEqual(n['parameters']['columns']['value']['contextJson'],'={{ $json.row.contextJson }}')
                elif n['name'] not in ['Prepare Retention Change','Render Change Preview','Validate Action','Render Choice','Parse Retention Command','Prepare Request']:
                    self.assertEqual(n,previous)
