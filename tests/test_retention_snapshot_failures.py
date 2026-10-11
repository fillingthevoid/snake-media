import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('snapshot_failures', ROOT / 'n8n/retention/snapshot_failures.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


class SnapshotFailureTests(unittest.TestCase):
    def test_idempotent_overlay_preserves_mutations_bindings_and_planner(self):
        source = json.loads((ROOT / 'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        original = copy.deepcopy(source)
        result = patch.build(source)
        self.assertEqual(source, original)
        self.assertEqual(result, patch.build(result))
        for old, new in zip(source, result):
            if old['id'] != 'snakeRetentionMediaV1':
                self.assertEqual(old, new)
                continue
            nodes = {n['name']: n for n in new['nodes']}
            for n in old['nodes']:
                if n['name'] in patch.READS:
                    self.assertEqual(n['parameters'], nodes[n['name']]['parameters'])
                    self.assertEqual(old['connections'][n['name']]['main'][0], new['connections'][n['name']]['main'][0])
                elif n['name'] not in ('Movie Snapshot Response', 'Series Snapshot Response',
                                       'Movie Still Exists?', 'Series Still Exists?',
                                       'Media Already Removed', 'Media Read Unavailable'):
                    self.assertEqual(n, nodes[n['name']])


if __name__ == '__main__':
    unittest.main()
