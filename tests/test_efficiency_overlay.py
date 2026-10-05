import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EfficiencyOverlayTests(unittest.TestCase):
    def patch(self):
        spec = importlib.util.spec_from_file_location('efficiency_patch', ROOT/'n8n/efficiency-pass/patch.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.patch_workflows(json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text()))

    def test_status_queries_only_actor_and_reuses_queues_without_catalogue_read(self):
        workflows = {w['id']: w for w in self.patch()}
        status = workflows['snakeStatusV1']
        nodes = {n['name']: n for n in status['nodes']}
        self.assertNotIn('Read Status Library', nodes)
        filters = nodes['Read Status Requests']['parameters']['filters']['conditions']
        self.assertEqual({f['keyName'] for f in filters}, {'source', 'userId', 'state'})
        self.assertTrue(all(f['condition']=='eq' for f in filters))
        self.assertIn('Read Shared Movie Queue', nodes)
        self.assertIn('Read Shared TV Queue', nodes)
        inspector = {n['name']: n for n in workflows['snakeStatusInspectV1']['nodes']}
        self.assertEqual(inspector['Read Status Target']['parameters']['workflowId']['value'], 'snakeTargetLibraryV1')
        self.assertIn('Status Queue Supplied?', inspector)

    def test_tracking_is_scoped_and_retention_safety_reads_remain(self):
        workflows = {w['id']: w for w in self.patch()}
        scan = {n['name']: n for n in workflows['snakeCompletionScanV1']['nodes']}
        self.assertEqual(scan['Tracked Requests']['parameters']['filters']['conditions'], [
            {'keyName':'state','condition':'eq','keyValue':'registered'},
            {'keyName':'baselineCaptured','condition':'isTrue'},
            {'keyName':'userId','condition':'neq','keyValue':'1'}])
        self.assertEqual(scan['Recent Download Events']['parameters']['filters']['conditions'][0]['keyValue'], '={{ $now.minus({minutes:30}).toISO() }}')
        conditions=scan['Completion Notices']['parameters']['filters']['conditions']
        self.assertIsInstance(conditions,list)
        self.assertEqual(len(conditions),200)
        self.assertTrue(all(c['keyName']=='requestKey' and c['condition']=='eq' for c in conditions))
        self.assertEqual(conditions[0]['keyValue'],'={{ $json.keys[0] ?? $json.keys[0] }}')
        self.assertEqual(scan['Completion Notices']['parameters']['matchType'], 'anyCondition')
        self.assertIn('Completion Request Batches', scan)
        retention = workflows['snakeRetentionScanV1']
        self.assertIn('Retention Has Requests?', {n['name'] for n in retention['nodes']})
        self.assertIn('Read Active Playback', {n['name'] for n in retention['nodes']})
        delete = workflows['snakeRetentionDeleteV1']
        self.assertIn('Recheck Active Playback', {n['name'] for n in delete['nodes']})

    def test_overlay_is_idempotent_preserves_credentials_and_has_valid_edges(self):
        workflows = self.patch()
        spec = importlib.util.spec_from_file_location('efficiency_patch', ROOT/'n8n/efficiency-pass/patch.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertEqual(module.patch_workflows(workflows), workflows)
        originals={w['id']:w for w in json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text())}
        for w in workflows:
            names={n['name'] for n in w['nodes']}
            self.assertEqual(len(names),len(w['nodes']))
            for ports in w['connections'].values():
                for edges in ports.values():
                    for group in edges:
                        for edge in group:self.assertIn(edge['node'],names)
            before={n['name']:n for n in originals[w['id']]['nodes']}
            for n in w['nodes']:
                if n['name'] in before and n['type'].endswith('.httpRequest'):
                    self.assertEqual(n['parameters'].get('headerParameters'),before[n['name']]['parameters'].get('headerParameters'))
