import json
import tempfile
import unittest
from pathlib import Path

from snake_media.admin_authorization import LiveUsers, replace_allowlist, grant_users
from dataclasses import replace
from unittest.mock import AsyncMock, patch
from snake_media.service import RequestService, TestBackend
from test_core import config


class AuthorizationTests(unittest.TestCase):
    def test_live_users_reload_and_corruption_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / 'users.json'
            users = LiveUsers({'111'}, str(p))
            self.assertIn('111', users)
            p.write_text(json.dumps({'version': 1, 'users': ['111', '222']}))
            self.assertIn('222', users)
            p.write_text('{invalid')
            self.assertNotIn('222', users)
            self.assertNotIn('111', users)

    def test_env_update_preserves_credentials_and_handles_duplicate_ids(self):
        original = '# comment\nDISCORD_TOKEN=private-test\nALLOWED_DISCORD_USER_IDS=111,222\nOTHER=value\n'
        result = replace_allowlist(original, ['222', '111', '222'])
        self.assertEqual(result, original)
        self.assertEqual(replace_allowlist(original, ['111', '222', '333']), original.replace('111,222', '111,222,333'))

    def test_only_owner_can_grant_and_invalid_ids_are_rejected(self):
        valid = dict(actor='111', channel='444', guild='555', user='222')
        self.assertEqual(grant_users(valid, {'111'}, {'444'}, {'111'}), ['111', '222'])
        for changes in [{'actor': '222'}, {'channel': '666'}, {'guild': None}, {'user': '0'}, {'user': str(2**64)}, {'user': '１２'}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                grant_users(valid | changes, {'111'}, {'444'}, {'111'})

    def test_ambiguous_env_does_not_get_rewritten(self):
        with self.assertRaises(ValueError):
            replace_allowlist('ALLOWED_DISCORD_USER_IDS=111\nALLOWED_DISCORD_USER_IDS=222\n', ['111'])


class AdministrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_nonowner_does_not_call_sync_helper(self):
        service = RequestService(replace(config(), admin_user_ids=frozenset({'111'}),
            admin_socket_path='/admin/test.sock'), TestBackend())
        with patch('snake_media.service.AdminClient') as client:
            reply = await service.authorize_user('222', '333', '444', '555')
        self.assertIn('Only', reply)
        client.assert_not_called()

    async def test_helper_failure_never_claims_success_or_logs_secret(self):
        service = RequestService(replace(config(), admin_user_ids=frozenset({'111'}),
            admin_socket_path='/admin/test.sock'), TestBackend())
        with patch('snake_media.service.AdminClient') as client:
            client.return_value.authorize = AsyncMock(side_effect=ValueError('private-credential'))
            with self.assertLogs('snake_media', level='ERROR') as logs:
                reply = await service.authorize_user('111', '333', '444', '555')
        self.assertIn('could not be confirmed', reply)
        self.assertNotIn('private-credential', ''.join(logs.output))
