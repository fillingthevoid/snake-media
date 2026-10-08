import copy
import importlib.util
import json
from pathlib import Path
import unittest
import subprocess

ROOT = Path(__file__).resolve().parents[1]


class RecommendationOverlay(unittest.TestCase):
    def build(self):
        spec = importlib.util.spec_from_file_location('recommend_patch', ROOT/'n8n/recommendations/patch.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text())
        return module, original, module.patch_workflows(original)

    def test_history_queries_are_owned_and_actions_use_atomic_claims(self):
        _, _, result = self.build()
        nodes = {n['name']: n for n in next(w for w in result if w['id']=='snakeRecommendV1')['nodes']}
        filters = nodes['Read Recommendation History']['parameters']['filters']['conditions']
        self.assertEqual({f['keyName'] for f in filters}, {'source', 'userId', 'state'})
        self.assertFalse(nodes['Read Recommendation History']['parameters']['returnAll'])
        self.assertLessEqual(nodes['Read Recommendation History']['parameters']['limit'], 200)
        for name in ['Claim Recommendation Choice', 'Save Recommendations']:
            keys = {f['keyName'] for f in nodes[name]['parameters']['filters']['conditions']}
            self.assertTrue({'id', 'state', 'claimId', 'source', 'userId', 'destinationId'} <= keys)

    def test_generated_suggestions_never_add_media_and_preserve_existing_preview(self):
        _, _, result = self.build()
        workflow = next(w for w in result if w['id']=='snakeRecommendV1')
        for node in workflow['nodes']:
            if node['type'].endswith('.httpRequest'):
                self.assertEqual(node['parameters'].get('method', 'GET'), 'GET')
            if node['type'].endswith('.executeWorkflow'):
                self.assertEqual(node['parameters']['workflowId']['value'], 'snakePreviewMediaV1')
        self.assertNotIn('global', json.dumps(workflow['connections']))

    def test_denied_choices_end_in_a_response_node_instead_of_an_empty_if_output(self):
        _, _, result = self.build()
        workflow = next(w for w in result if w['id']=='snakeRecommendV1')
        nodes = {n['name']: n for n in workflow['nodes']}
        for check in ['Recommendation Choice Valid?', 'Recommendation Claimed?']:
            target = workflow['connections'][check]['main'][1][0]['node']
            self.assertEqual(nodes[target]['type'], 'n8n-nodes-base.code')

    def test_skipped_candidate_does_not_mix_the_next_title_with_previous_metadata(self):
        _, _, result = self.build()
        workflow = next(w for w in result if w['id']=='snakeRecommendV1')
        nodes = {n['name']: n for n in workflow['nodes']}
        body = nodes['Match Recommendation Library Item']['parameters']['jsCode']
        script = r'''
const code=JSON.parse(require('fs').readFileSync(0,'utf8'));
const rows=[{type:'movie',item:{media:{tmdbId:5}}},{type:'movie',item:null},
 {type:'movie',item:{media:{tmdbId:9,title:'Alien',year:1979}}}];
const $=name=>name==='Recommendation Batches'?{context:{currentRunIndex:2}}:
 {first:(_branch,index)=>({json:rows[index]})};
const result=new Function('$','$json','$runIndex',code)($,
 {Items:[{Id:'abc',ProviderIds:{Tmdb:'9'},Path:'/data/movies/Alien.mkv'}]},1);
console.log(JSON.stringify(result));
'''
        completed = subprocess.run(['node','-e',script],input=json.dumps(body),text=True,capture_output=True)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(json.loads(completed.stdout)[0]['json']['libraryId'],'abc')

    def test_telegram_recommendation_cards_have_poster_and_dynamic_buttons(self):
        _, original, result = self.build()
        workflow = next(w for w in result if w['id']=='snakeTelegramCardV1')
        nodes = {n['name']: n for n in workflow['nodes']}
        sender = nodes['Send Recommendation Poster']
        self.assertEqual(sender['parameters']['operation'], 'sendPhoto')
        self.assertIsInstance(sender['parameters']['inlineKeyboard']['rows'], str)
        self.assertIn('keyboard.rows', sender['parameters']['inlineKeyboard']['rows'])
        text = nodes['Send Recommendation Text']
        self.assertEqual(text['parameters']['operation'], 'sendMessage')
        self.assertEqual(sender['credentials'], text['credentials'])

    def test_overlay_preserves_credentials_and_authorization_and_is_idempotent(self):
        module, original, result = self.build()
        self.assertEqual(module.patch_workflows(result), result)
        before = {w['id']: w for w in original}
        after = {w['id']: w for w in result}
        for wid, authorization in [('HXtTzVTrpNZMZVt3', 'Authorized Request?'), ('0e67KTcphqxEKNsh', 'Authorized User?')]:
            self.assertEqual(before[wid]['connections'][authorization], after[wid]['connections'][authorization])
            old = {n['name']: n for n in before[wid]['nodes']}
            for node in after[wid]['nodes']:
                if node['name'] in old:
                    self.assertEqual(node.get('credentials'), old[node['name']].get('credentials'))
        for workflow in result:
            names = {n['name'] for n in workflow['nodes']}
            self.assertEqual(len(names), len(workflow['nodes']))
            for source, outputs in workflow['connections'].items():
                self.assertIn(source, names)
                for groups in outputs.values():
                    for edges in groups:
                        for edge in edges:
                            self.assertIn(edge['node'], names)
