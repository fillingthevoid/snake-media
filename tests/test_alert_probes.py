import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('alert_probes',Path(__file__).resolve().parents[1]/'tools/alert_probes.py')
probes=importlib.util.module_from_spec(spec);spec.loader.exec_module(probes)


class ProbeTests(unittest.TestCase):
    def test_pool_capacity_not_main_rollover_and_unknown_never_means_healthy(self):
        snapshot={'version':1,'checkedAt':1000000,'services':{s:True for s in probes.SERVICES},'storage':{'guard':True,'disks':[{'label':'Main','freeGiB':1},{'label':'SSD','freeGiB':200},{'label':'Pool','freeGiB':201}]}}
        facts=probes.health_facts(snapshot,1000)
        self.assertTrue(facts['storage:space']);self.assertTrue(facts['storage:mounts'])
        snapshot['storage']['disks'][2]['freeGiB']=40
        self.assertFalse(probes.health_facts(snapshot,1000)['storage:space'])
        self.assertIsNone(probes.health_facts(snapshot,1500)['storage:space'])
        self.assertFalse(probes.health_facts(snapshot,1500)['monitor:health'])
        snapshot['checkedAt']=1000000;snapshot['services']['Jellyfin']=False
        self.assertFalse(probes.health_facts(snapshot,1000)['service:Jellyfin'])

    def test_malformed_health_sections_are_unknown(self):
        facts=probes.health_facts({'version':1,'checkedAt':1000000,'services':None},1000)
        self.assertFalse(facts['monitor:health'])
        self.assertIsNone(facts['service:Jellyfin'])

    def test_failed_or_stale_backup_and_running_backup_not_false_recovery(self):
        self.assertFalse(probes.backup_fact({'Result':'exit-code','ActiveState':'failed'},1000,900))
        self.assertFalse(probes.backup_fact({'Result':'success','ActiveState':'inactive'},200000,1000))
        self.assertTrue(probes.backup_fact({'Result':'success','ActiveState':'inactive'},1000,900))
        self.assertIsNone(probes.backup_fact({'Result':'success','ActiveState':'activating'},1000,900))
        self.assertIsNone(probes.backup_fact({},1000,900))

    def test_n8n_probe_reads_stuck_owner_and_only_owned_current_discord_confirmations(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'metadata.sqlite'
            with closing(sqlite3.connect(path)) as db:
                db.execute('create table data_table (id text,name text)')
                db.executemany('insert into data_table values (?,?)',[('pending','snake_media_pending'),('control','snake_media_retention_control')])
                db.execute('create table data_table_user_control (key text,owner text)')
                db.execute("insert into data_table_user_control values ('global','4')")
                db.execute('create table execution_entity (id text,startedAt text,status text,workflowId text,deletedAt text)')
                db.execute("insert into execution_entity values ('4','2026-10-05T00:00:00Z','running','snakeRetentionCoordinatorV1',NULL)")
                db.execute('create table data_table_user_pending (id integer,source text,userId text,state text,updatedAt text,expiresAt text,mediaJson text)')
                row=(12,'discord','2','processing','2026-10-05T00:00:00Z','2026-10-05T01:00:00Z',json.dumps({'title':'Example'}))
                db.executemany('insert into data_table_user_pending values (?,?,?,?,?,?,?)',[row,(13,*row[1:2],'9',*row[3:]),(14,'telegram',*row[2:]),(15,*row[1:5],'2026-10-04T00:00:00Z',row[-1])])
                db.commit()
            import datetime
            now=datetime.datetime(2026,10,5,0,20,tzinfo=datetime.timezone.utc).timestamp()
            result=probes.n8n_probe(path,now,{'2'})
            self.assertFalse(result['lock']);self.assertFalse(result['requests']['12']['healthy'])
            self.assertIsNone(result['requests']['15']['healthy'])
            self.assertNotIn('13',result['requests']);self.assertNotIn('14',result['requests'])
            self.assertEqual(result['requests']['12']['userId'],'2')
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute('select owner from data_table_user_control').fetchone()[0],'4')

    def test_missing_metadata_fails_closed_without_creating_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'missing.sqlite';result=probes.n8n_probe(path,1000,{'2'})
            self.assertFalse(result['available']);self.assertIsNone(result['lock']);self.assertFalse(path.exists())
