import importlib.util,json,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class GuidedOverlay(unittest.TestCase):
    def test_overlay_is_idempotent_authorization_stays_first_and_retention_is_unchanged(self):
        spec=importlib.util.spec_from_file_location('guided',ROOT/'n8n/guided-navigation/patch.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        source=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        result=mod.build(source);self.assertEqual(result,mod.build(result))
        old={w['id']:w for w in source};new={w['id']:w for w in result}
        for wid in old:
            if wid not in mod.IDS:self.assertEqual(old[wid],new[wid])
            nodes={n['name']:n for n in new[wid]['nodes']}
            for n in old[wid]['nodes']:
                self.assertEqual(n.get('credentials'),nodes[n['name']].get('credentials'))
                if n['name'].startswith(('Authorized ','Claim ','Save ')):self.assertEqual(n,nodes[n['name']])
        w=new['0e67KTcphqxEKNsh']
        status_node=next(n for n in new['snakeStatusInspectV1']['nodes'] if n['name']=='Describe Status')
        self.assertIn('function scopedQueue',status_node['parameters']['jsCode'])
        self.assertEqual(w['connections']['Authorized User?']['main'][0][0]['node'],'Resolve Guided Reply')
        for w in result:
            names={n['name'] for n in w['nodes']}
            for v in w['connections'].values():
                for ports in v.values():
                    for es in ports:
                        for e in es:self.assertIn(e['node'],names)
        code=[n['parameters']['jsCode'] for w in result for n in w['nodes'] if n['type'].endswith('.code')]
        p=subprocess.run(['node','-e',"for(const s of JSON.parse(require('fs').readFileSync(0,'utf8')))new Function(s);"],input=json.dumps(code),text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)
