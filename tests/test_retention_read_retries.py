import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RetentionReadRetryTests(unittest.TestCase):
    def test_only_scan_gets_retry_and_private_bindings_survive(self):
        spec = importlib.util.spec_from_file_location('read_retry', ROOT / 'n8n/retention/read_retries.py')
        patch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(patch)
        source = json.loads((ROOT / 'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        for workflow in source:
            for node in workflow['nodes']:
                if (workflow['id'], node['name']) in patch.READS:
                    for key in ('retryOnFail', 'maxTries', 'waitBetweenTries'):
                        node.pop(key, None)
        before = copy.deepcopy(source)
        result = patch.build(source)
        self.assertEqual(source, before)
        self.assertEqual(patch.build(result), result)
        changed = []
        for old, new in zip(before, result):
            self.assertEqual(old['connections'], new['connections'])
            for left, right in zip(old['nodes'], new['nodes']):
                self.assertEqual(left['parameters'], right['parameters'])
                if left != right:
                    changed.append((old['id'], left['name']))
                    self.assertEqual(left['type'], 'n8n-nodes-base.httpRequest')
                    self.assertEqual(left['parameters'].get('method', 'GET'), 'GET')
                    self.assertTrue(right['retryOnFail'])
                    self.assertEqual(right['maxTries'], 3)
                    self.assertEqual(right['waitBetweenTries'], 1000)
        self.assertEqual(set(changed), patch.READS)


if __name__ == '__main__':
    unittest.main()
