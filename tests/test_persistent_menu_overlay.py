import json,subprocess,unittest
from test_watch_overlay import ROOT,module


class PersistentMenus(unittest.TestCase):
    def test_overlay_only_changes_navigation_and_compaction_and_preserves_claims(self):
        before=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        p=module('persistent-menus');after=p.build(before);self.assertEqual(after,p.build(after))
        by={w['id']:w for w in after}
        for w in before:
            if w['id'] not in p.CHANGED_IDS:self.assertEqual(w,by[w['id']])
        nodes={n['name']:n for n in by['snakeMyRequestsV1']['nodes']};claim=nodes['Claim Request Selection']['parameters']
        self.assertEqual({f['keyName'] for f in claim['filters']['conditions']},{'id','state','claimId','source','userId','destinationId'})
        self.assertIn('expiresAt',claim['columns']['value'])
        code=[n['parameters']['jsCode'] for wid in p.CHANGED_IDS for n in by[wid]['nodes'] if n['type'].endswith('.code')]
        result=subprocess.run(['node','-e',"for(const s of JSON.parse(require('fs').readFileSync(0,'utf8')))new Function(s);"],input=json.dumps(code),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
