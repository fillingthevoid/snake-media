import copy,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class UsabilityOverlay(unittest.TestCase):
    def build(self):
        spec=importlib.util.spec_from_file_location('usability_patch',ROOT/'n8n/request-usability/patch.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        before=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        return module,before,module.build(before)

    def test_overlay_is_idempotent_and_preserves_private_installation_bindings(self):
        module,before,after=self.build()
        self.assertEqual(module.build(after),after)
        old={w['id']:w for w in before}
        for w in after:
            previous={n['name']:n for n in old[w['id']]['nodes']}
            for n in w['nodes']:
                if n['name'] not in previous:continue
                p=previous[n['name']]
                self.assertEqual(n.get('credentials'),p.get('credentials'))
                if 'Authorized' in n['name'] or 'Allowlist' in n['name']:
                    self.assertEqual(n,p)
                if n['type'].endswith('.httpRequest'):
                    self.assertEqual(n['parameters'],p['parameters'])

    def test_claim_persists_selected_media_and_categories_only_read_native_tables(self):
        _,_,after=self.build();by={w['id']:w for w in after}
        nodes={n['name']:n for n in by['snakeConfirmMediaV1']['nodes']}
        self.assertIn('mediaJson',nodes['Claim Choice']['parameters']['columns']['value'])
        self.assertIn('revise(',nodes['Validate Action']['parameters']['jsCode'])
        n={n['name']:n for n in by['snakeMyRequestsV1']['nodes']}
        for name in ['Read Menu Retention','Read Menu Download Events','Read Menu Notices']:
            self.assertTrue(n[name]['type'].endswith('.dataTable'))
            self.assertEqual(n[name]['parameters']['operation'],'get')
            self.assertLessEqual(n[name]['parameters']['limit'],3000)
        self.assertIn("$('Read My Requests').all()",n['Create Request Menu']['parameters']['jsCode'])
        self.assertEqual(by['snakeMyRequestsV1']['connections']['Read My Requests']['main'][0][0]['node'],'Menu Retention Input')
        for name in ['Menu Retention Input','Menu Events Input','Menu Notices Input']:
            self.assertEqual(n[name]['parameters']['jsCode'],'return [{json:{}}];')
        self.assertIn('match_',next(n for n in by['snakePreviewMediaV1']['nodes'] if n['name']=='Render Preview')['parameters']['jsCode'])

    def test_telegram_preserves_posters_and_all_new_choices_in_dynamic_card_route(self):
        _,_,after=self.build();w=next(w for w in after if w['id']=='snakeTelegramCardV1')
        n={n['name']:n for n in w['nodes']}
        self.assertIn('wrong',n['Recommendation Card?']['parameters']['conditions']['conditions'][0]['leftValue'])
        self.assertIn('menuChoices',n['Recommendation Card Data']['parameters']['jsCode'])
        self.assertIn('choices',n['Recommendation Card Data']['parameters']['jsCode'])
