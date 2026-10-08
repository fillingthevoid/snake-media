import importlib.util,json,subprocess,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def module(folder):
    spec=importlib.util.spec_from_file_location(folder,ROOT/('n8n/'+folder+'/patch.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


class WatchOverlay(unittest.TestCase):
    def test_saved_addresses_reach_replies_and_both_completion_transports(self):
        original=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        my=module('my-requests');before=my.build(original);p=module('watch-preferences');result=p.build(before)
        self.assertEqual(result,p.build(result));old={w['id']:w for w in before};new={w['id']:w for w in result}
        helper={n['name']:n for n in new['snakeWatchPreferenceV1']['nodes']}
        filters=helper['Read Watch Setting']['parameters']['filters']['conditions'];self.assertEqual({x['keyName'] for x in filters},{'source','userId','state'})
        self.assertEqual(helper['Read Watch Setting']['parameters']['limit'],1)
        queue=new['snakeNotificationQueueV1'];self.assertEqual(queue['connections']['Queue Has Watch Items?']['main'][1][0]['node'],'Queue Response')
        delivery=new['snakeTelegramNoticeSendV1'];self.assertEqual(delivery['connections']['Apply Notice Watch Preference']['main'][0][0]['node'],'Completion Card Metadata')
        for wid in old:
            if wid not in p.CHANGED_IDS:self.assertEqual(old[wid],new[wid])
            previous={n['name']:n for n in old[wid]['nodes']}
            for n in new[wid]['nodes']:
                if n['name'] in previous and n['name']!='Completion Card Metadata':self.assertEqual(n.get('credentials'),previous[n['name']].get('credentials'))
        code=[]
        for w in result:
            names={n['name'] for n in w['nodes']};self.assertEqual(len(names),len(w['nodes']))
            for outputs in w['connections'].values():
                for branches in outputs.values():
                    for branch in branches:
                        for e in branch:self.assertIn(e['node'],names)
            code.extend(n['parameters']['jsCode'] for n in w['nodes'] if n['type'].endswith('.code'))
        run=subprocess.run(['node','-e',"for(const s of JSON.parse(require('fs').readFileSync(0,'utf8')))new Function(s);"],input=json.dumps(code),capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
