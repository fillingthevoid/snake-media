import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('short_locks',ROOT/'n8n/retention-locks/patch.py')
patch=importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


class ShortRetentionLocksTests(unittest.TestCase):
    def source(self):
        return json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))

    def test_group_wrapper_does_not_shorten_the_existing_reconciliation_budget(self):
        rows={w['id']:w for w in patch.build(self.source())}
        group=rows['snakeRetentionGroupV1']['settings']['executionTimeout']
        worker=rows['snakeRetentionMediaV1']['settings']['executionTimeout']
        coordinator=rows['snakeRetentionCoordinatorV1']['settings']['executionTimeout']
        self.assertGreaterEqual(group,min(worker,coordinator))
        self.assertLessEqual(group,coordinator)

    def test_read_scan_bypasses_lock_and_each_title_uses_coordinator(self):
        source=self.source();before=copy.deepcopy(source);rows=patch.build(source);w={w['id']:w for w in rows}
        self.assertEqual(source,before)
        c=w['snakeRetentionCoordinatorV1'];n={n['name']:n for n in c['nodes']}
        self.assertEqual(c['connections']['Coordinator Input']['main'][0][0]['node'],'Scan Job?')
        self.assertEqual(c['connections']['Scan Job?']['main'][0][0]['node'],'Run Unlocked Scan')
        self.assertEqual(c['connections']['Scan Job?']['main'][1][0]['node'],'Read Global Lock')
        scan={n['name']:n for n in w['snakeRetentionScanV1']['nodes']}
        self.assertEqual(scan['Process Each Retention Group']['parameters']['workflowId']['value'],c['id'])
        self.assertEqual(n['Run Locked Scan']['parameters']['workflowId']['value'],'snakeRetentionGroupV1')
        self.assertEqual(n['Run Locked Scan']['onError'],'continueErrorOutput')
        self.assertFalse(n['Run Locked Scan'].get('alwaysOutputData',False))
        self.assertEqual(patch.build(rows),rows)

    def test_failure_release_uses_native_nodes_and_exact_owner_condition(self):
        c=next(w for w in patch.build(self.source()) if w['id']=='snakeRetentionCoordinatorV1');ns={n['name']:n for n in c['nodes']}
        for name in ['Read Failed Phase','Safe Planning Failure?','Release Safe Failed Lock','Safe Failed Lock Released?','Safe Planning Failure Result','Uncertain Mutation Result']:
            self.assertNotEqual(ns[name]['type'],'n8n-nodes-base.code')
        release=ns['Release Safe Failed Lock']['parameters']
        self.assertTrue(any(f['keyName']=='owner' and '$execution.id' in f['keyValue'] for f in release['filters']['conditions']))
        self.assertIn(':preparing',json.dumps(ns['Safe Planning Failure?']['parameters']))
        self.assertEqual(c['connections']['Safe Planning Failure?']['main'][1][0]['node'],'Uncertain Mutation Result')
        for name in ['Verify Global Lock','Locked Input','Save Locked Result','Return Locked Result']:
            self.assertNotEqual(ns[name]['type'],'n8n-nodes-base.code')
        self.assertEqual(c['connections']['Release Global Lock']['main'][0][0]['node'],'Global Lock Released?')
        self.assertNotIn('busy:true',ns['Uncertain Mutation Result']['parameters']['jsonOutput'])

    def test_claim_refresh_and_mutation_barrier_preserve_media_api_nodes(self):
        source=self.source();rows=patch.build(source);old={w['id']:w for w in source};new={w['id']:w for w in rows}
        group=new['snakeRetentionGroupV1'];names={n['name'] for n in group['nodes']}
        self.assertTrue({'Read Current Group Requests','Read Current Group Records','Read Current Group Mode','Refresh Group Claims','One Group Record Read'}<=names)
        self.assertEqual(group['connections']['Read Current Group Requests']['main'][0][0]['node'],'One Group Record Read')
        worker=new['snakeRetentionMediaV1']
        self.assertEqual(worker['connections']['Plan Retention']['main'][0][0]['node'],'Mark Retention Mutation')
        prev={n['name']:n for n in old['snakeRetentionMediaV1']['nodes']}
        for n in worker['nodes']:
            if n['type']=='n8n-nodes-base.httpRequest':self.assertEqual(n,prev[n['name']])
        for wid in ['snakeRetentionDeleteV1','snakeCommitMediaBodyV2','snakeRetentionChangeApplyV1']:
            self.assertEqual(old[wid],new[wid])
