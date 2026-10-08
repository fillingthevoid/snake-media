import json, subprocess, unittest
from test_watch_overlay import ROOT,module


class ActiveOverlay(unittest.TestCase):
    def test_update_success_acknowledges_and_retry_never_sends_a_new_post(self):
        source=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        before=module('watch-preferences').build(module('my-requests').build(source))
        p=module('active-cards');result=p.build(before);self.assertEqual(result,p.build(result))
        by={w['id']:w for w in result};w=by['snakeTelegramNoticeSendV1']
        self.assertEqual(w['connections']['Original Telegram Card Updated?']['main'][0][0]['node'],'Remember Telegram Completion Card')
        self.assertEqual(w['connections']['Original Telegram Card Retry?']['main'][0][0]['node'],'Retry Original Telegram Card')
        self.assertNotIn('Retry Original Telegram Card',w['connections'])
        self.assertEqual(w['connections']['Restore Original Completion Metadata']['main'][0][0]['node'],'Completion Retention Controls?')
        code=[]
        for workflow in result:
            self.assertEqual(len({n['id'] for n in workflow['nodes']}),len(workflow['nodes']))
            names={n['name'] for n in workflow['nodes']}
            for outputs in workflow['connections'].values():
                for branches in outputs.values():
                    for branch in branches:
                        for edge in branch:self.assertIn(edge['node'],names)
            code.extend(n['parameters']['jsCode'] for n in workflow['nodes'] if n['type'].endswith('.code'))
        run=subprocess.run(['node','-e',"for(const s of JSON.parse(require('fs').readFileSync(0,'utf8')))new Function(s);"],input=json.dumps(code),capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
