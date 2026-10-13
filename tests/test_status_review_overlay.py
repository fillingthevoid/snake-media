import copy,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class StatusReviewOverlayTests(unittest.TestCase):
    def test_direct_status_carries_actor_and_creates_owned_menu_without_recursive_reads(self):
        s=importlib.util.spec_from_file_location('direct',ROOT/'n8n/status-review/patch.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
        old=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text());new=m.build(old)
        self.assertEqual(new,m.build(new));by={w['id']:w for w in new}
        actor=next(n for n in by['HXtTzVTrpNZMZVt3']['nodes'] if n['name']=='Prepare Status Actor')['parameters']['jsCode']
        for key in ['destinationId','messageId','requestedAt']:self.assertIn(key,actor)
        self.assertEqual(by['snakeStatusV1']['connections']['Format Status Result']['main'][0][0]['node'],'Status Review Context')
        w=by['snakeStatusReviewCardV1'];self.assertEqual(len([n for n in w['nodes'] if n['type'].endswith('.httpRequest')]),0)
        self.assertEqual(len([n for n in w['nodes'] if n['type'].endswith('.executeWorkflow')]),0)
        for before,after in zip(old,new):
            self.assertEqual(before.get('id'),after.get('id'))
            for original in before['nodes']:
                n=next(n for n in after['nodes'] if n['name']==original['name'])
                self.assertEqual(n.get('credentials'),original.get('credentials'))
                if original['type'].endswith('.httpRequest'):self.assertEqual(n,original)
