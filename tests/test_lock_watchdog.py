import importlib.util
import sqlite3
import unittest
from pathlib import Path

path=Path(__file__).parents[1]/'n8n/lock-recovery/watchdog.py'
spec=importlib.util.spec_from_file_location('watchdog',path)
watchdog=importlib.util.module_from_spec(spec);spec.loader.exec_module(watchdog)

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.executescript('''CREATE TABLE data_table(name TEXT,id TEXT);
        INSERT INTO data_table VALUES ('snake_media_retention_control','test');
        CREATE TABLE data_table_user_test(key TEXT,owner TEXT);
        INSERT INTO data_table_user_test VALUES ('global','12');
        CREATE TABLE execution_entity(id INTEGER,workflowId TEXT,status TEXT,stoppedAt TEXT,deletedAt TEXT);
        INSERT INTO execution_entity VALUES (12,'snakeRetentionCoordinatorV1','error','2026-10-01 10:00:00',NULL);''')
        self.now=watchdog.timestamp('2026-10-01T10:05:00Z')
    def tearDown(self):self.c.close()
    def test_terminal_owner_requires_cooldown_and_no_active_executions(self):
        self.assertEqual(watchdog.inspect(self.c,self.now)['state'],'ready')
        self.assertEqual(watchdog.inspect(self.c,self.now-250)['state'],'waiting')
        self.c.execute("INSERT INTO execution_entity VALUES (13,'unrelated','waiting',NULL,NULL)")
        self.assertEqual(watchdog.inspect(self.c,self.now)['state'],'waiting')
    def test_unknown_running_pruned_and_malformed_owners_are_never_recovered(self):
        for status in ['running','new','waiting','unknown']:
            self.c.execute('UPDATE execution_entity SET status=?',(status,))
            self.assertNotEqual(watchdog.inspect(self.c,self.now)['state'],'ready')
        self.c.execute("UPDATE execution_entity SET status='error',stoppedAt=NULL")
        self.assertNotEqual(watchdog.inspect(self.c,self.now)['state'],'ready')
        self.c.execute('DELETE FROM execution_entity')
        self.assertEqual(watchdog.inspect(self.c,self.now)['state'],'blocked')
        self.c.execute("UPDATE data_table_user_test SET owner='unexplained'")
        self.assertEqual(watchdog.inspect(self.c,self.now)['state'],'blocked')
        self.c.execute("UPDATE data_table_user_test SET owner=''")
        self.assertEqual(watchdog.inspect(self.c,self.now)['state'],'idle')
    def test_only_known_workflows_and_terminal_recovery_owners_are_eligible(self):
        self.c.execute("UPDATE execution_entity SET workflowId='unrelated'")
        self.assertEqual(watchdog.inspect(self.c,self.now)['state'],'blocked')
        self.c.execute("UPDATE execution_entity SET workflowId='snakeLockRecoveryV1',status='crashed'")
        result=watchdog.inspect(self.c,self.now)
        self.assertEqual(result['state'],'ready')
        self.assertEqual(result['proof']['owner'],'12')
