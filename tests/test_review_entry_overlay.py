import copy,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ReviewEntryOverlayTests(unittest.TestCase):
    def test_unrelated_workflows_and_private_bindings_are_preserved(self):
        spec=importlib.util.spec_from_file_location('entry',ROOT/'n8n/review-entry/patch.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        rows=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text())
        extra=copy.deepcopy(next(w for w in rows if w['id']=='snakeMyRequestsV1'));extra['id']='unrelatedReviewTest'
        for n in extra['nodes']:
            code=n.get('parameters',{}).get('jsCode')
            if code:n['parameters']['jsCode']=code.replace("out.choices.push({label:'Review',action:'mr_review'})","out.choices.push({label:'LEGACY',action:'mr_review'})")
        source=rows+[extra]
        env={'ALLOWED_DISCORD_USER_IDS':'10','ADMIN_DISCORD_USER_IDS':'10','ALLOWED_DISCORD_CHANNEL_IDS':'30'}
        out=m.build(source,env);self.assertEqual(out[-1],extra);self.assertEqual(out,m.build(out,env))
        for before,after in zip(source,out):
            for original,n in zip(before['nodes'],after['nodes']):
                if before['id']=='snakeMediaReviewsV1':continue
                self.assertEqual(original.get('credentials'),n.get('credentials'))
                if original['type'].endswith('.httpRequest'):self.assertEqual(original,n)
