import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

from snake_media.confirmations import CUSTOM_ID
from snake_media.n8n_client import N8NError, format_result

ROOT = Path(__file__).resolve().parents[1]


class StatusMatchNavigationTests(unittest.TestCase):
    def bundle(self):
        return json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))

    def test_discord_accepts_only_named_search_navigation_buttons(self):
        for action in ['mr_next', 'mr_previous']:
            with self.subTest(action=action):
                self.assertIsNotNone(CUSTOM_ID.fullmatch('snake:7:'+action))
                result = format_result({'version':1, 'status':'confirmation', 'pendingId':'7', 'text':'Match 2 of 3', 'choices':[{'label':'Next', 'action':action}]})
                self.assertEqual(result.choices[0]['action'], action)
        with self.assertRaises(N8NError):
            format_result({'version':1, 'status':'confirmation', 'pendingId':'7', 'text':'Match', 'choices':[{'label':'Next', 'action':'mr_next_999'}]})

    def test_native_platform_routes_queries_and_callbacks(self):
        by = {w['id']:w for w in self.bundle()}
        for wid, prep, dest in [('HXtTzVTrpNZMZVt3','Validate Discord Request','channelId'), ('0e67KTcphqxEKNsh','Prepare Request','chatId')]:
            nodes = {n['name']:n for n in by[wid]['nodes']}
            gate = nodes['My Requests Command?']['parameters']['conditions']['conditions'][0]['leftValue'][3:-3].strip()
            callback = nodes['My Requests Callback?']['parameters']['conditions']['conditions'][0]['leftValue'][3:-3].strip()
            actor = nodes['Prepare My Requests Actor']['parameters']['jsCode']
            script = "const assert=require('node:assert/strict');let text='',action='';const $=()=>({first:()=>({json:{text,userId:'111',"+dest+":'333',messageId:'444',requestedAt:'2026-10-15T15:00:00Z'}})});const $json={};"
            script += "for(text of ['/status','/status Ninja Turtles','/status@SnakeMediaBot Ninja Turtles'])assert.equal(("+gate+"),true);text='/status Ninja Turtles';const result=(new Function('$',"+json.dumps(actor)+"))($)[0].json;assert.equal(result.query,'Ninja Turtles');"
            script += "for(action of ['mr_next','mr_previous']){$json.action=action;assert.equal(("+callback+"),true);}text='/statusx turtles';assert.equal(("+gate+"),false);"
            result = subprocess.run(['node','-e',script],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr)

    def test_initial_selected_menu_reads_exact_status_and_reused_menu_refreshes(self):
        w = next(w for w in self.bundle() if w['id']=='snakeMyRequestsV1')
        nodes = {n['name']:n for n in w['nodes']}
        self.assertIn('Initial Request Status?',list(nodes))
        for parent in ['Store Request Menu','Existing Request Menu']:
            self.assertEqual(w['connections'][parent]['main'][0][0]['node'],'Initial Request Status?')
        self.assertEqual(nodes['Read Initial Request Status']['parameters']['workflowId']['value'],'snakeStatusV1')
        self.assertNotIn('Verify Request Claim',nodes['Render Initial Request Status']['parameters']['jsCode'])
        self.assertTrue(nodes['Read My Requests']['parameters']['returnAll'])
        # Conditional callback claims and ownership filters remain intact.
        keys={c['keyName'] for c in nodes['Claim Request Selection']['parameters']['filters']['conditions']}
        self.assertTrue({'id','state','claimId','source','userId','destinationId'} <= keys)

    def test_overlay_is_idempotent_and_preserves_private_bindings_and_write_nodes(self):
        spec=importlib.util.spec_from_file_location('status_match_overlay',ROOT/'n8n/status-match-navigation/patch.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        old=self.bundle()
        new=module.build(old)
        self.assertEqual(new,module.build(new))
        for before,after in zip(old,new):
            nodes={n['name']:n for n in after['nodes']}
            for original in before['nodes']:
                n=nodes[original['name']]
                self.assertEqual(n.get('credentials'),original.get('credentials'))
                if original['type'].endswith('.httpRequest'):
                    self.assertEqual(n,original)
                if original['type'].endswith('.dataTable'):
                    self.assertEqual(n['parameters'].get('dataTableId'),original['parameters'].get('dataTableId'))
                    if original['parameters'].get('operation')!='get':self.assertEqual(n,original)

    def test_initial_workflow_nodes_render_first_exact_match_without_callback_claim(self):
        w=next(w for w in self.bundle() if w['id']=='snakeMyRequestsV1')
        nodes={n['name']:n for n in w['nodes']}
        script="""const assert=require('node:assert/strict'),p=require('./n8n/my-requests/policy.js');
        const now=Date.now(),actor={source:'telegram',userId:'111',destinationId:'333',messageId:'444',query:'Turtles',requestedAt:new Date(now).toISOString()};
        const row={...p.create(actor,[{...actor,state:'registered',requestKey:'r1',mediaType:'movie',mediaId:'10',title:'Ninja Turtles'}],now),id:7};
        """
        script+="const exact=(new Function('$json',"+json.dumps(nodes['Prepare Initial Request Status']['parameters']['jsCode'])+"))(row)[0].json;assert.deepEqual(exact,{source:'telegram',userId:'111',query:'',mediaType:'movie',mediaId:'10'});"
        script+="const $=()=>({first:()=>({json:row})});const result=(new Function('$json','$',"+json.dumps(nodes['Render Initial Request Status']['parameters']['jsCode'])+"))({summaryText:'Movie title (1990)\\nAvailable'},$)[0].json;assert.match(result.text,/Match 1 of 1/);assert.match(result.text,/1990/);assert.equal(result.pendingId,'7');assert.ok(!result.actionAccepted);"
        run=subprocess.run(['node','-e',script],capture_output=True,text=True,encoding='utf-8',cwd=ROOT)
        self.assertEqual(run.returncode,0,run.stderr)


if __name__=='__main__':
    unittest.main()
