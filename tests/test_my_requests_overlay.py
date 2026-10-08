import importlib.util,json,subprocess,unittest
from pathlib import Path
from snake_media.confirmations import CUSTOM_ID,presentation
from snake_media.n8n_client import format_result,N8NError

ROOT=Path(__file__).resolve().parents[1]


class MyRequests(unittest.TestCase):
    def build(self):
        spec=importlib.util.spec_from_file_location('my_requests',ROOT/'n8n/my-requests/patch.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        original=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        return m,original,m.build(original)

    def test_bounded_callbacks_render_and_reject_other_actions(self):
        for action in ['mr_title_199','mr_page_24','mr_refresh','mr_extend','mr_keep','mr_back','mr_close']:
            self.assertIsNotNone(CUSTOM_ID.fullmatch('snake:12:'+action))
            reply=format_result({'version':1,'status':'confirmation','text':'Your request','pendingId':'12','choices':[{'label':'Action','action':action}]})
            self.assertEqual(presentation(reply)['view'].children[0].custom_id,'snake:12:'+action)
        for action in ['mr_title_1000','mr_page_100','mr_delete']:
            self.assertIsNone(CUSTOM_ID.fullmatch('snake:12:'+action))

    def test_native_queries_and_claims_remain_owned_and_graph_compiles(self):
        m,old,result=self.build();self.assertEqual(result,m.build(result))
        before={w['id']:w for w in old};after={w['id']:w for w in result}
        for wid in before:
            if wid not in m.CHANGED_IDS:self.assertEqual(before[wid],after[wid])
        for wid,name in [('HXtTzVTrpNZMZVt3','Authorized Request?'),('0e67KTcphqxEKNsh','Authorized User?')]:
            self.assertEqual(before[wid]['connections'][name],after[wid]['connections'][name])
        workflow=after['snakeMyRequestsV1'];nodes={n['name']:n for n in workflow['nodes']}
        keys={f['keyName'] for f in nodes['Claim Request Selection']['parameters']['filters']['conditions']}
        self.assertEqual(keys,{'id','state','claimId','source','userId','destinationId'})
        self.assertEqual(nodes['Read My Requests']['parameters']['limit'],200)
        self.assertEqual(nodes['Preview Request Expiry']['parameters']['workflowId']['value'],'snakeRetentionChangePreviewV1')
        self.assertFalse(any(n['type'].endswith('.httpRequest') for n in workflow['nodes']))
        bodies=[]
        for w in result:
            names={n['name'] for n in w['nodes']};self.assertEqual(len(names),len(w['nodes']))
            for outputs in w['connections'].values():
                for groups in outputs.values():
                    for group in groups:
                        for edge in group:self.assertIn(edge['node'],names)
            for n in w['nodes']:
                if n['type'].endswith('.code'):bodies.append(n['parameters']['jsCode'])
                if w['id'] in before:
                    oldnode=next((x for x in before[w['id']]['nodes'] if x['name']==n['name']),None)
                    if oldnode:self.assertEqual(n.get('credentials'),oldnode.get('credentials'))
        run=subprocess.run(['node','-e',"for(const s of JSON.parse(require('fs').readFileSync(0,'utf8')))new Function(s);"],input=json.dumps(bodies),capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
