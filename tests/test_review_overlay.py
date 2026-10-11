import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('review_fixes', ROOT / 'n8n/review-fixes/patch.py')
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)


class ReviewOverlayTests(unittest.TestCase):
    def bundle(self):
        return json.loads((ROOT / 'config-templates/n8n-current-media-workflows.json').read_text())

    def test_repeated_overlay_is_unchanged_and_input_is_not_mutated(self):
        source = self.bundle()
        original = copy.deepcopy(source)
        once = overlay.build(source)
        self.assertEqual(source, original)
        self.assertEqual(overlay.build(once), once)

    def test_private_installation_bindings_and_other_policies_survive(self):
        source = self.bundle()
        commit = next(w for w in source if w['name'] == 'Snake Media - Commit Media Under Lock')
        commit.update(active=True, versionId='private-version', settings={'executionTimeout': 600})
        nodes = {n['name']: n for n in commit['nodes']}
        search = nodes['Search Confirmed Movie']
        search['parameters']['url'] = 'https://radarr.example.test/api/v3/command'
        search['parameters']['headerParameters']['parameters'][0]['value'] = '__SYNTHETIC_PRIVATE_HEADER__'
        search['credentials'] = {'httpHeaderAuth': {'id': 'private-credential', 'name': 'Private'}}
        nodes['Find Confirmed Movie']['credentials'] = copy.deepcopy(search['credentials'])
        original = copy.deepcopy(source)
        after = overlay.build(source)
        updated = next(w for w in after if w['id'] == commit['id'])
        changed_nodes = {n['name']: n for n in updated['nodes']}
        self.assertTrue(updated['active'])
        self.assertEqual(updated['settings'], {'executionTimeout': 600})
        self.assertEqual(updated['versionId'], 'private-version')
        restore = changed_nodes['Restore Requested Movie Monitoring']
        self.assertEqual(restore['parameters']['url'], 'https://radarr.example.test/api/v3/movie/editor')
        self.assertEqual(restore['credentials'], search['credentials'])
        self.assertEqual(restore['parameters']['headerParameters'], search['parameters']['headerParameters'])
        self.assertIn('https://radarr.example.test/api/v3/movie/', changed_nodes['Read Requested Movie Monitoring']['parameters']['url'])
        for name in ['Register Movie Before Search', 'Save Movie Subscription', 'Complete Pending',
                     'Selected Episode Snapshot', 'Build Movie Payload', 'Build Series Payload']:
            self.assertEqual(changed_nodes[name], nodes[name])
        # The unrelated workflow graphs and metadata, including multi-season
        # selection/subscription code, must be preserved by the targeted overlay.
        for before, result in zip(original, after):
            self.assertEqual(before['id'], result['id'])
            if before['id'] != commit['id']:
                self.assertEqual(before['connections'], result['connections'])
                for left, right in zip(before['nodes'], result['nodes']):
                    if overlay.RETENTION_MARKER not in left.get('parameters', {}).get('jsCode', ''):
                        self.assertEqual(left, right)

    def test_unknown_existing_movie_route_is_rejected_before_preparing_output(self):
        source = self.bundle()
        commit = next(w for w in source if w['name'] == 'Snake Media - Commit Media Under Lock')
        commit['connections']['Movie Missing?']['main'][0][0]['node'] = 'Movie Result'
        with self.assertRaisesRegex(ValueError, 'Unknown missing-movie route'):
            overlay.build(source)
