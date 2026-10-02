"""Release checks must reject credential-bearing exports without exposing values."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


class PublicReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'tools/check_public_release.py'
        spec = importlib.util.spec_from_file_location('release_check', path)
        cls.check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.check)

    def scan(self, value):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'workflow.json').write_text(json.dumps(value), encoding='utf-8')
            return self.check.scan(root)

    def test_literal_api_key_is_rejected_without_echoing_value(self):
        secret = 'synthetic-api-key-only-for-this-test'
        issues = self.scan({'headerParameters': {'parameters': [{'name': 'X-Api-Key', 'value': secret}]}})
        self.assertTrue(issues)
        self.assertNotIn(secret, str(issues))

    def test_placeholders_and_credential_expressions_are_allowed(self):
        for value in ['__SERVER_HEADER__', '={{ $credentials.apiKey }}']:
            self.assertEqual(self.scan({'headerParameters': {'parameters': [{'name': 'X-Api-Key', 'value': value}]}}), [])

    def test_instance_credential_binding_and_pinned_data_are_rejected(self):
        self.assertTrue(self.scan({'credentials': {'telegramApi': {'id': 'instance-id', 'name': 'Account'}}}))
        self.assertTrue(self.scan({'pinData': {'Request': [{'json': {'text': 'private request'}}]}}))
        self.assertEqual(self.scan({'credentials': {'telegramApi': {'id': 'CONFIGURE_TELEGRAMAPI', 'name': 'Configure telegramApi'}}}), [])

    def test_private_env_and_state_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('DISCORD_TOKEN=synthetic', encoding='utf-8')
            (root / 'receipts.sqlite3').write_bytes(b'private state')
            self.assertEqual(len(self.check.scan(root)), 2)
