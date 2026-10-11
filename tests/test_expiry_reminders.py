import copy,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ReminderWorkflowTests(unittest.TestCase):
 def test_native_graph_preserves_scan_result_and_uses_current_bound_tables(self):
  ws=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text());by={w['id']:w for w in ws}
  spec=importlib.util.spec_from_file_location('reminders',ROOT/'n8n/expiry-reminders/patch.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  output=m.apply(ws)
  # A repeated overlay must not create extra nodes/edges or change policies.
  self.assertEqual(output,ws)
  reminder=by[m.ID];self.assertFalse(any('http' in n['type'].lower() for n in reminder['nodes']))
  self.assertEqual(by['snakeRetentionScanV1']['connections']['Scan Summary']['main'][0][0]['node'],'Queue Expiry Reminders')
  store=next(n for n in reminder['nodes'] if n['name']=='Store Expiry Reminder')
  self.assertEqual(store['parameters']['operation'],'upsert')
  self.assertEqual(store['parameters']['filters']['conditions'][0]['keyName'],'notificationKey')
  sender=by['snakeTelegramNoticeSendV1']
  self.assertEqual(sender['connections']['New Telegram Reminder?']['main'][0][0]['node'],'Completion Retention Controls?')
  self.assertEqual(sender['connections']['New Telegram Reminder?']['main'][1][0]['node'],'Update Original Telegram Request')
