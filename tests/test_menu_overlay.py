import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


class MenuOverlay(unittest.TestCase):
    def setUp(self):
        self.source=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        spec=importlib.util.spec_from_file_location('menu_patch',ROOT/'n8n/menu-simplification/patch.py')
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.result=self.module.build(self.source)

    def test_overlay_preserves_authorization_credentials_claims_and_is_idempotent(self):
        self.assertEqual(self.result,self.module.build(self.result))
        old={w['id']:w for w in self.source};new={w['id']:w for w in self.result}
        for wid in old:
            if wid not in self.module.IDS:
                self.assertEqual(old[wid],new[wid]);continue
            nodes={n['name']:n for n in new[wid]['nodes']}
            for n in old[wid]['nodes']:
                self.assertEqual(n.get('credentials'),nodes[n['name']].get('credentials'))
                if n['name'].startswith(('Claim ', 'Save ', 'Authorized ')):
                    self.assertEqual(n,nodes[n['name']])
            if wid!='snakeTelegramCardV1':self.assertEqual(old[wid]['connections'],new[wid]['connections'])

    def test_shared_native_help_and_genre_keyboard_compile_and_render(self):
        rows={w['id']:w for w in self.result}
        body=next(n for n in rows['snakeTelegramCardV1']['nodes'] if n['name']=='Recommendation Card Data')['parameters']['jsCode']
        script="const body=JSON.parse(require('fs').readFileSync(0,'utf8'));const choices=Array.from({length:17},(_,i)=>({label:'Genre '+i,action:'rec_genre_'+i}));choices.push({label:'Cancel',action:'rec_cancel'});const r=new Function('$json',body)({choices,pendingId:'12'});console.log(JSON.stringify(r[0].json.keyboard.rows));"
        run=subprocess.run(['node','-e',script],input=json.dumps(body),capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        widths=[len(x['row']['buttons']) for x in json.loads(run.stdout)]
        self.assertEqual(widths,[3,3,3,3,3,2,1])
        all_code=[n['parameters']['jsCode'] for w in self.result for n in w['nodes'] if n['type'].endswith('.code')]
        run=subprocess.run(['node','-e',"for(const b of JSON.parse(require('fs').readFileSync(0,'utf8')))new Function(b);"],input=json.dumps(all_code),capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        help_body=next(n for n in rows['0e67KTcphqxEKNsh']['nodes'] if n['name']=='Prepare Request')['parameters']['jsCode']
        script="const body=JSON.parse(require('fs').readFileSync(0,'utf8'));const r=new Function('$json',body)({message:{text:'/help',message_id:1,date:1700000000,chat:{id:333},from:{id:111}}});console.log(JSON.stringify(r[0].json));"
        run=subprocess.run(['node','-e',script],input=json.dumps(help_body),capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        r=json.loads(run.stdout);self.assertLess(len(r['commandReply']),350)
        self.assertEqual([c['label'] for c in r['menuChoices']][:3],['Request','Recommend','My requests'])
