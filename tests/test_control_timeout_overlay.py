import json, subprocess, unittest
from test_watch_overlay import ROOT, module


class TimeoutOverlay(unittest.TestCase):
    def test_targeted_overlay_keeps_bindings_and_is_idempotent(self):
        before=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        p=module('control-timeouts');after=p.build(before)
        self.assertEqual(after,p.build(after))
        by={w['id']:w for w in after}
        for w in before:
            if w['id'] not in p.CHANGED_IDS:self.assertEqual(w,by[w['id']])
            old={n['name']:n for n in w['nodes']}
            for n in by[w['id']]['nodes']:
                if n['name'] in old:self.assertEqual(n.get('credentials'),old[n['name']].get('credentials'))
        schedule=next(n for n in by['snakeTelegramControlsRetryV1']['nodes'] if n['type'].endswith('.scheduleTrigger'))
        self.assertEqual(schedule['parameters']['rule']['interval'],[{'field':'seconds','secondsInterval':30}])
        self.assertIn('expiresAt',p.node(by['snakeConfirmMediaV1'],'Claim Choice')['parameters']['columns']['value'])
        codes=[n['parameters']['jsCode'] for w in after for n in w['nodes'] if n['type'].endswith('.code')]
        result=subprocess.run(['node','-e',"for(const s of JSON.parse(require('fs').readFileSync(0,'utf8')))new Function(s);"],input=json.dumps(codes),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
