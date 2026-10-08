import json,subprocess,unittest
from test_watch_overlay import ROOT,module


class ReusableExpiry(unittest.TestCase):
    def test_only_owned_preview_and_cleanup_boundaries_change(self):
        before=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        p=module('reusable-expiry-controls');after=p.build(before);self.assertEqual(after,p.build(after));by={w['id']:w for w in after}
        for w in before:
            if w['id'] not in p.CHANGED_IDS:self.assertEqual(w,by[w['id']])
            original={n['name']:n for n in w['nodes']}
            for n in by[w['id']]['nodes']:self.assertEqual(n.get('credentials'),original[n['name']].get('credentials'))
        n=next(n for n in by['snakeMyRequestsV1']['nodes'] if n['name']=='Accept Request Expiry');self.assertIn('preserveOriginalControls:true',n['parameters']['jsCode'])
        code=[n['parameters']['jsCode'] for wid in p.CHANGED_IDS for n in by[wid]['nodes'] if n['type'].endswith('.code')]
        r=subprocess.run(['node','-e',"for(const s of JSON.parse(require('fs').readFileSync(0,'utf8')))new Function(s);"],input=json.dumps(code),capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
