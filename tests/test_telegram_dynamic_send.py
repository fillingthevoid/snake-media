import copy
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('dynamic_send', Path(__file__).resolve().parents[1] / 'n8n/button-feedback/dynamic_send.py')
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)


class TelegramDynamicSendTests(unittest.TestCase):
    def test_preserves_credentials_and_fallbacks_without_mutating_source(self):
        sender = {'name': 'Poster', 'type': 'n8n-nodes-base.telegram', 'typeVersion': 1.2,
                  'parameters': {'operation': 'sendPhoto', 'inlineKeyboard': {'rows': '={{ $json.keyboard.rows }}'}},
                  'credentials': {'telegramApi': {'id': 'private-binding'}}, 'onError': 'continueRegularOutput'}
        source = [{'id': 'snakeTelegramCardV1', 'nodes': [sender], 'connections': {'Poster': {'main': [[]]}}}]
        before = copy.deepcopy(source)
        result = overlay.build(source)
        self.assertEqual(source, before)
        node = result[0]['nodes'][0]
        self.assertEqual(node['parameters'], {'operation': 'sendCard', 'sendMode': 'photo'})
        self.assertEqual(node['credentials'], sender['credentials'])
        self.assertEqual(node['onError'], sender['onError'])
        self.assertEqual(result[0]['connections'], source[0]['connections'])
        self.assertEqual(overlay.build(result), result)
