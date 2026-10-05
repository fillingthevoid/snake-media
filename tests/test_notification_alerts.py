from contextlib import closing
import datetime
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import alert_probes as probes
import server_alerts as alerts

NOW = datetime.datetime(2026, 10, 5, 12, tzinfo=datetime.timezone.utc).timestamp()


class NotificationAlertTests(unittest.TestCase):
    def fixture(self, path):
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE data_table (id text, name text)')
            db.executemany('INSERT INTO data_table VALUES (?,?)', [('notices', 'snake_media_notifications'), ('requests', 'snake_media_requests')])
            db.execute('CREATE TABLE data_table_user_notices (id integer, requestKey text, source text, state text, createdAt text)')
            db.execute('CREATE TABLE data_table_user_requests (requestKey text, source text, userId text, title text, state text, baselineCaptured integer)')
            db.executemany('INSERT INTO data_table_user_requests VALUES (?,?,?,?,?,?)', [
                ('discord:real', 'discord', '123456789012345678', 'A movie', 'registered', 1),
                ('telegram:real', 'telegram', '42', 'A series', 'registered', 1),
                ('discord:test', 'discord', '1', 'Test', 'registered', 1)])
            db.executemany('INSERT INTO data_table_user_notices VALUES (?,?,?,?,?)', [
                (1, 'discord:real', 'discord', 'pending', '2026-10-05T11:40:00Z'),
                (2, 'telegram:real', 'telegram', 'pending', '2026-10-05T11:40:00Z'),
                (3, 'discord:real', 'discord', 'pending', '2026-10-05T11:55:00Z'),
                (4, 'discord:test', 'discord', 'pending', '2026-10-05T11:40:00Z'),
                (5, 'discord:real', 'telegram', 'pending', '2026-10-05T11:40:00Z'),
                (6, 'discord:real', 'discord', 'pending', 'invalid'),
                (7, 'discord:real', 'discord', 'pending', '2026-10-05T13:00:00Z')])
            db.commit()

    def test_both_platforms_age_without_reading_payload_or_changing_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'n8n.sqlite'
            self.fixture(path)
            result = probes.notification_probe(path, NOW)
            self.assertTrue(result['available'])
            self.assertFalse(result['notices']['1']['healthy'])
            self.assertFalse(probes.notification_probe(path, NOW, observed_ids=['1'])['notices']['1']['healthy'])
            self.assertFalse(result['notices']['2']['healthy'])
            self.assertTrue(result['notices']['3']['healthy'])
            self.assertNotIn('4', result['notices'])
            self.assertNotIn('5', result['notices'])
            self.assertIsNone(result['notices']['6']['healthy'])
            self.assertIsNone(result['notices']['7']['healthy'])
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM data_table_user_notices WHERE state='pending'").fetchone()[0], 7)
                db.execute("UPDATE data_table_user_notices SET state='delivered' WHERE id=1")
                db.commit()
            self.assertTrue(probes.notification_probe(path, NOW, observed_ids=['1'])['notices']['1']['healthy'])
            self.assertNotIn('1', probes.notification_probe(path, NOW)['notices'])

    def test_missing_or_overflow_metadata_stays_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'missing.sqlite'
            self.assertFalse(probes.notification_probe(path, NOW)['available'])
            self.assertFalse(path.exists())
            self.fixture(path)
            self.assertFalse(probes.notification_probe(path, NOW, limit=2)['available'])

    def test_owner_routing_recovery_and_saved_deduplication(self):
        ops = {'available': True, 'lock': True, 'requests': {},
               'notifications': {'available': True, 'notices': {'1': {'source': 'telegram', 'title': 'A series', 'healthy': False}}}}
        state = {'schema': 1, 'issues': {}}
        facts, recipients, titles = alerts.observations(None, ops, True, '123456789012345678', set(), state['issues'], NOW)
        self.assertEqual(recipients['notification:1'], ['123456789012345678'])
        self.assertFalse(facts['notification:1'])
        alerts.policy.observe(state['issues'], facts, recipients, NOW)
        events = alerts.policy.observe(state['issues'], facts, recipients, NOW + 300)
        event = next(e for e in events if e['key'] == 'notification:1')
        text = alerts.render([event], titles)
        self.assertIn('Telegram', text)
        self.assertIn('A series', text)
        self.assertIn('retries', text.lower())
        alerts.policy.delivered(state['issues'], event, NOW + 300)
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'state.json'
            alerts.save_state(p, state)
            restored = alerts.load_state(p)
            self.assertFalse(any(e['key'] == 'notification:1' for e in alerts.policy.observe(restored['issues'], facts, recipients, NOW + 600)))
            ops['notifications'] = {'available': False, 'notices': {}}
            unknown, routes, _ = alerts.observations(None, ops, True, '123456789012345678', set(), restored['issues'], NOW + 900)
            self.assertIsNone(unknown['notification:1'])
            self.assertFalse(any(e['key'] == 'notification:1' for e in alerts.policy.observe(restored['issues'], unknown, routes, NOW + 900)))
            facts['notification:1'] = True
            alerts.policy.observe(restored['issues'], facts, recipients, NOW + 1200)
            recovery = alerts.policy.observe(restored['issues'], facts, recipients, NOW + 1500)
            self.assertEqual(next(e for e in recovery if e['key'] == 'notification:1')['kind'], 'recovery')
