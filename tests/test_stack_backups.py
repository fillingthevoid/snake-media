import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest


class StackBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'tools/stack_backup.py'
        spec = importlib.util.spec_from_file_location('stack_backup', path)
        cls.backup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.backup)

    def test_online_snapshot_includes_wal_and_does_not_change_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'live.sqlite'
            target = Path(folder) / 'snapshot.sqlite'
            with closing(sqlite3.connect(source)) as db:
                db.execute('pragma journal_mode=wal')
                db.execute('create table sample (value text)')
                db.execute('insert into sample values (?)', ('saved',))
                db.commit()
                self.backup.snapshot_database(source, target)
                with closing(sqlite3.connect(target)) as saved:
                    self.assertEqual(saved.execute('select value from sample').fetchall(), [('saved',)])
                self.assertEqual(db.execute('select count(*) from sample').fetchone()[0], 1)

    def test_workflow_export_removes_state_and_credentials_and_replaces_private_values(self):
        secret = 'synthetic-secret-only-for-testing'
        workflow = {'id': 'media-workflow', 'name': 'Snake Media - Example', 'active': True,
                    'pinData': {'private': 'a request'}, 'staticData': {'private': 'state'},
                    'nodes': [{'name': 'HTTP', 'credentials': {'httpHeaderAuth': {'id': 'native-id', 'name': 'Private account'}},
                               'parameters': {'url': 'http://192.168.50.12:7878/api/v3/movie',
                                              'headerParameters': {'parameters': [{'name': 'X-Api-Key', 'value': secret}]},
                                              'jsCode': 'const key="' + secret + '";const owner="987654321098765432";'}}]}
        cleaned = self.backup.sanitize_workflows([workflow], {secret})
        serialized = json.dumps(cleaned)
        for private in [secret, '192.168.50.12', '987654321098765432', 'Private account', 'native-id', 'a request']:
            self.assertNotIn(private, serialized)
        self.assertFalse(cleaned[0]['active'])
        self.assertNotIn('pinData', cleaned[0])
        self.assertEqual(workflow['nodes'][0]['parameters']['headerParameters']['parameters'][0]['value'], secret)

    def test_settings_export_uses_allowlists_and_drops_provider_credentials(self):
        rows = [{'name': 'Private account', 'implementation': 'Newznab', 'enableRss': True, 'priority': 3,
                 'fields': [{'name': 'apiKey', 'value': 'secret'}, {'name': 'username', 'value': 'private-user'},
                            {'name': 'categories', 'value': [5000]}], 'password': 'private'}]
        cleaned = self.backup.public_settings('indexer', rows)
        text = json.dumps(cleaned)
        for private in ['secret', 'private-user', 'Private account', 'password']:
            self.assertNotIn(private, text)
        self.assertEqual(cleaned[0]['fields'], [{'name': 'categories', 'value': [5000]}])

    def test_manifest_verification_detects_changed_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            file = root / 'config.xml'
            file.write_text('original', encoding='utf-8')
            manifest = self.backup.build_manifest(root)
            self.backup.verify_files(root, manifest)
            file.write_text('changed', encoding='utf-8')
            with self.assertRaises(ValueError):
                self.backup.verify_files(root, manifest)
