import importlib.util,unittest
from pathlib import Path
class EnableDeletionTests(unittest.TestCase):
 def test_internal_mode_switch_requires_unique_empty_lock_and_preview_mode(self):
  s=importlib.util.spec_from_file_location('enable',Path(__file__).resolve().parents[1]/'tools/enable_retention_workflow.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
  from datetime import datetime,timezone
  w=m.build(datetime(2026,10,10,23,55,tzinfo=timezone.utc),'control')
  ns={n['name']:n for n in w['nodes']}
  self.assertFalse(any('webhook' in n['type'] or 'http' in n['type'] for n in w['nodes']))
  self.assertEqual(w['settings']['timezone'],'UTC')
  self.assertIn(".all().length===1",ns['Unique Free Lock?']['parameters']['conditions']['conditions'][0]['leftValue'])
  self.assertIn(".all().length===1",ns['Preview Mode?']['parameters']['conditions']['conditions'][0]['leftValue'])
  values=ns['Enable Deletion']['parameters']['columns']['value'];self.assertEqual(values,{'owner':'enabled'})
  self.assertEqual(ns['Enable Deletion']['parameters']['filters']['conditions'][1]['keyValue'],'preview')
  self.assertEqual(w['connections']['Preview Mode?']['main'][1][0]['node'],'Release Enable Lock')
