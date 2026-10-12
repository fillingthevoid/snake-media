import importlib.util,json,unittest
from pathlib import Path
class RequestEntryOverlayTests(unittest.TestCase):
    def test_idempotent_overlay_preserves_graphs_credentials_and_native_http_nodes(self):
        spec=importlib.util.spec_from_file_location('entry',Path('n8n/request-entry/patch.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        source=json.loads(Path('config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        out=m.build(source);self.assertEqual(out,source)
        for w,old in zip(out,source):
            self.assertEqual(w['connections'],old['connections'])
            for n,on in zip(w['nodes'],old['nodes']):
                self.assertEqual(n.get('credentials'),on.get('credentials'))
                if on['type'].endswith('.httpRequest'):self.assertEqual(n,on)
        wrapper=next(w for w in out if w['id']=='snakeCommitMediaV1')
        self.assertEqual(wrapper['connections']['Coordinate Commit']['main'][0][0]['node'],'Inspect Commit Result?')
