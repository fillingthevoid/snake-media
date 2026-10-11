"""Behavioral regressions for processing expiry and notification-history turnover."""
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

NOW = datetime.datetime(2026, 10, 9, tzinfo=datetime.timezone.utc).timestamp()


def stamp(seconds):
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).isoformat()


class ReviewAlertTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'metadata.sqlite'
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('CREATE TABLE data_table(id text,name text)')
            db.executemany('INSERT INTO data_table VALUES(?,?)', [
                ('pending', 'snake_media_pending'), ('control', 'snake_media_retention_control'),
                ('notices', 'snake_media_notifications'), ('requests', 'snake_media_requests')])
            db.execute('CREATE TABLE data_table_user_control(key text,owner text)')
            db.execute("INSERT INTO data_table_user_control VALUES('global','')")
            db.execute('CREATE TABLE data_table_user_pending(id integer,source text,userId text,state text,updatedAt text,expiresAt text,mediaJson text)')
            db.execute('CREATE TABLE data_table_user_notices(id integer,requestKey text,source text,state text,createdAt text)')
            db.execute('CREATE TABLE data_table_user_requests(requestKey text,source text,userId text,title text,state text,baselineCaptured integer)')
            db.commit()

    def processing(self, updated, expiry):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DELETE FROM data_table_user_pending')
            db.execute('INSERT INTO data_table_user_pending VALUES(?,?,?,?,?,?,?)',
                       (12, 'discord', '2', 'processing', updated, expiry, '{"title":"Example"}'))
            db.commit()

    def test_processing_is_monitored_after_interactive_expiry(self):
        self.processing(stamp(NOW), stamp(NOW + 300))
        for age, expected in [(0, True), (300, True), (899, True), (900, False), (1200, False)]:
            with self.subTest(age=age):
                result = probes.n8n_probe(self.path, NOW + age, {'2'})
                self.assertIs(result['requests']['12']['healthy'], expected)

    def test_old_future_and_invalid_processing_cannot_trigger_alerts(self):
        for updated, expiry in [
                (stamp(NOW - 86401), stamp(NOW - 86101)),
                (stamp(NOW + 60), stamp(NOW + 360)),
                (stamp(NOW - 1200), stamp(NOW - 1500)),
                ('invalid', stamp(NOW + 300)), (stamp(NOW), 'invalid')]:
            with self.subTest(updated=updated, expiry=expiry):
                self.processing(updated, expiry)
                self.assertIsNone(probes.n8n_probe(self.path, NOW, {'2'})['requests']['12']['healthy'])

    def observation(self, issues, notices, now, available=True):
        ops = {'available': True, 'lock': True, 'requests': {},
               'notifications': {'available': available, 'notices': notices}}
        facts, recipients, _ = alerts.observations(None, ops, True, '2', {'2'}, issues, now)
        return alerts.policy.observe(issues, facts, recipients, now)

    def test_healthy_notice_turnover_does_not_accumulate_history(self):
        issues = {}
        for i in range(1, 2102):
            self.observation(issues, {str(i): {'healthy': True, 'source': 'discord', 'title': 'Example'}}, NOW + i)
        notice_keys = [r['key'] for r in issues.values() if r['key'].startswith('notification:')]
        self.assertLessEqual(len(notice_keys), 1)

    def test_loading_legacy_history_retires_healthy_rows_but_keeps_incidents(self):
        issues = {}
        alerts.policy.observe(issues, {'notification:' + str(i): True for i in range(1, 2002)},
                              {'notification:' + str(i): ['2'] for i in range(1, 2002)}, NOW)
        self.observation(issues, {'3000': {'healthy': False, 'source': 'telegram', 'title': 'Stalled'}}, NOW + 1)
        events = self.observation(issues, {'3000': {'healthy': False, 'source': 'telegram', 'title': 'Stalled'}}, NOW + 301)
        event = next(e for e in events if e['key'] == 'notification:3000')
        alerts.policy.delivered(issues, event, NOW + 301)
        # Simulate persisted history from the old implementation.
        healthy = {}
        alerts.policy.observe(healthy, {'notification:' + str(i): True for i in range(1, 2002)},
                              {'notification:' + str(i): ['2'] for i in range(1, 2002)}, NOW)
        issues.update(healthy)
        state_path = Path(self.folder.name) / 'alerts.json'
        alerts.save_state(state_path, {'schema': 1, 'issues': issues})
        restored = alerts.load_state(state_path)['issues']
        self.assertEqual([r['key'] for r in restored.values() if r['key'].startswith('notification:')], ['notification:3000'])
        self.observation(restored, {}, NOW + 601, available=False)
        self.assertTrue(restored['notification:3000:2']['active'])
        self.observation(restored, {'3000': {'healthy': True, 'source': 'telegram', 'title': 'Stalled'}}, NOW + 901)
        recoveries = self.observation(restored, {'3000': {'healthy': True, 'source': 'telegram', 'title': 'Stalled'}}, NOW + 1201)
        recovery = next(e for e in recoveries if e['key'] == 'notification:3000')
        self.assertEqual(recovery['kind'], 'recovery')
        alerts.policy.delivered(restored, recovery, NOW + 1201)
        alerts.save_state(state_path, {'schema': 1, 'issues': restored})
        self.assertNotIn('notification:3000:2', alerts.load_state(state_path)['issues'])

    def test_many_unresolved_watched_ids_do_not_disable_recovery_reads(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("INSERT INTO data_table_user_requests VALUES('real','discord','2','Example','registered',1)")
            db.execute('INSERT INTO data_table_user_notices VALUES(?,?,?,?,?)',
                       (2501, 'real', 'discord', 'delivered', stamp(NOW - 1200)))
            db.commit()
        result = probes.notification_probe(self.path, NOW, [str(i) for i in range(1, 2502)])
        self.assertTrue(result['available'])
        self.assertIs(result['notices']['2501']['healthy'], True)

    def test_pending_problem_survives_history_cleanup_and_unknown_readings(self):
        issues = {}
        notices = {'9': {'healthy': False, 'source': 'discord', 'title': 'Example'}}
        self.observation(issues, notices, NOW)
        event = next(e for e in self.observation(issues, notices, NOW + 300) if e['key'] == 'notification:9')
        path = Path(self.folder.name) / 'pending.json'
        alerts.save_state(path, {'schema': 1, 'issues': issues})
        restored = alerts.load_state(path)['issues']
        self.assertEqual(restored['notification:9:2']['pending'], event)
        self.assertFalse(restored['notification:9:2']['active'])
        self.observation(restored, {}, NOW + 600, available=False)
        self.assertEqual(restored['notification:9:2']['pending'], event)
