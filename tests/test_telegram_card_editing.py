import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TelegramCardEditingTests(unittest.TestCase):
    def test_overlay_preserves_private_policy_and_routes_cards_through_editor(self):
        spec = importlib.util.spec_from_file_location('edit_cards', ROOT / 'n8n/button-feedback/edit_cards.py')
        patch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(patch)
        source = json.loads((ROOT / 'config-templates/n8n-current-media-workflows.json').read_text())
        source = [w for w in source if w['id'] in ('0e67KTcphqxEKNsh', 'snakeTelegramCardV1')]
        before = copy.deepcopy(source)
        root = next(w for w in source if w['id'] == '0e67KTcphqxEKNsh')
        auth = next(n for n in root['nodes'] if n['name'] == 'Authorized User?')
        auth['parameters']['conditions']['conditions'][0]['leftValue'] = 'private authorization expression'
        before = copy.deepcopy(source)
        result = patch.build(source)
        self.assertEqual(source, before)
        self.assertEqual(result, patch.build(result))
        root = next(w for w in result if w['id'] == '0e67KTcphqxEKNsh')
        self.assertEqual(next(n for n in root['nodes'] if n['name'] == 'Authorized User?'), auth)
        card = next(w for w in result if w['id'] == 'snakeTelegramCardV1')
        edge = card['connections']['Validate Card']['main'][0][0]
        self.assertEqual(edge['node'], 'Present Telegram Card')
        sender = next(n for n in card['nodes'] if n['name'] == edge['node'])
        self.assertEqual(sender['type'], 'CUSTOM.snakeTelegramControls')
        self.assertEqual(sender['parameters']['operation'], 'presentCard')
        self.assertEqual(sender['credentials'], next(n for n in card['nodes'] if n['name'] == 'Send Shared Menu')['credentials'])
