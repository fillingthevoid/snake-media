import importlib.util,json,unittest,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(folder):
    s=importlib.util.spec_from_file_location(folder,ROOT/'n8n'/folder/'patch.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class DeliveryFixOverlayTests(unittest.TestCase):
    def source(self):return json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
    def test_completion_overlay_keeps_verification_and_private_http_bindings(self):
        old=self.source();m=load('completion-fallback');out=m.build(old);self.assertEqual(out,m.build(out))
        for before,after in zip(old,out):
            if before['id'] not in m.SHARED_IDS:self.assertEqual(before,after);continue
            self.assertEqual(before['connections'],after['connections'])
            for a,b in zip(before['nodes'],after['nodes']):
                if a['type'].endswith('.httpRequest'):self.assertEqual(a['parameters'],b['parameters']);self.assertEqual(a.get('credentials'),b.get('credentials'))
                if before['id']!='snakeQueueCandidateV1':
                    clean=lambda n:re.sub(r'function poster\(media\)\{[^\n]*\}','ARTWORK_PARSER',json.dumps(n,ensure_ascii=False).replace('\\n','\n'))
                    self.assertEqual(clean(a),clean(b))
    def test_review_reference_deletion_and_rebinding_use_exact_snapshot_guards(self):
        old=self.source();m=load('review-comment-recovery');out=m.build(old);self.assertEqual(out,m.build(out))
        for a,b in zip(old,out):
            if a['id']!='snakeMediaReviewsV1':self.assertEqual(a,b)
        w=next(w for w in out if w['id']=='snakeMediaReviewsV1');ns={n['name']:n for n in w['nodes']}
        delete=ns['Delete Confirmed Review Comment']['parameters'];self.assertEqual(delete['operation'],'deleteRows')
        self.assertEqual({x['keyName'] for x in delete['filters']['conditions']},{'id','requestKey','contextJson','source','state'})
        rebind=ns['Update Existing Review Post']['parameters'];self.assertEqual(rebind['operation'],'update')
        self.assertEqual({x['keyName'] for x in rebind['filters']['conditions']},{'id','requestKey','contextJson','source','state'})
        self.assertEqual(w['connections']['Review Decision']['main'][0][0]['node'],'Review Comment Delete?')
        self.assertEqual(w['connections']['Review Comment Delete?']['main'][1][0]['node'],'Review Write?')
