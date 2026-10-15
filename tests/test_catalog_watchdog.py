import hashlib,importlib.util,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('catalog_watchdog',ROOT/'n8n/lock-recovery/watchdog.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)

class CatalogWatchdogTests(unittest.TestCase):
    def test_previously_verified_catalog_versions_remain_safe_after_a_reviewed_upgrade(self):
        with tempfile.TemporaryDirectory() as folder,sqlite3.connect(':memory:') as c:
            c.executescript('CREATE TABLE workflow_entity(id TEXT,activeVersionId TEXT,settings TEXT);CREATE TABLE workflow_history(workflowId TEXT,versionId TEXT,nodes TEXT,connections TEXT);CREATE TABLE execution_entity(id TEXT,workflowId TEXT,workflowVersionId TEXT,status TEXT,startedAt TEXT,stoppedAt TEXT,deletedAt TEXT);CREATE TABLE execution_data(executionId TEXT,data TEXT);')
            versions=[]
            for version in ['v1','v2']:
                nodes=[{'name':version}];value={'nodes':nodes,'connections':{},'settings':{}}
                versions.append({'versionId':version,'settings':{},'sha256':hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()})
                c.execute('INSERT INTO workflow_history VALUES (?,?,?,?)',('snakeReviewCatalogV1',version,json.dumps(nodes),'{}'))
            c.execute('INSERT INTO workflow_entity VALUES (?,?,?)',('snakeReviewCatalogV1','v2','{}'))
            c.execute('INSERT INTO execution_entity VALUES (?,?,?,?,?,?,?)',('1','snakeReviewCatalogV1','v1','running','2026-10-15',None,'2026-10-15'))
            pin=Path(folder)/'pin.json';pin.write_text(json.dumps({'workflowId':'snakeReviewCatalogV1',**versions[1],'versions':versions}))
            with patch.object(w,'CATALOG_PIN_PATH',pin):
                self.assertEqual(w.activity_count(c,2000000000),0)
                versions[1]['sha256']='unverified';pin.write_text(json.dumps({'workflowId':'snakeReviewCatalogV1',**versions[1],'versions':versions}));self.assertEqual(w.activity_count(c,2000000000),1)

    def test_only_exact_verified_catalog_version_is_nonblocking(self):
        with tempfile.TemporaryDirectory() as folder,sqlite3.connect(':memory:') as c:
            c.executescript('CREATE TABLE workflow_entity(id TEXT,activeVersionId TEXT,settings TEXT);CREATE TABLE workflow_history(workflowId TEXT,versionId TEXT,nodes TEXT,connections TEXT);CREATE TABLE execution_entity(id TEXT,workflowId TEXT,workflowVersionId TEXT,status TEXT,startedAt TEXT,stoppedAt TEXT,deletedAt TEXT);CREATE TABLE execution_data(executionId TEXT,data TEXT);')
            nodes=[{'name':'Known safe catalog','type':'n8n-nodes-base.code','parameters':{'jsCode':'return [];'}}];connections={}
            encoded=json.dumps({'nodes':nodes,'connections':connections,'settings':{}},sort_keys=True,separators=(',',':'))
            pin=Path(folder)/'pin.json';pin.write_text(json.dumps({'workflowId':'snakeReviewCatalogV1','versionId':'verified-v1','sha256':hashlib.sha256(encoded.encode()).hexdigest()}))
            c.execute('INSERT INTO workflow_entity VALUES (?,?,?)',('snakeReviewCatalogV1','verified-v1','{}'))
            c.execute('INSERT INTO workflow_history VALUES (?,?,?,?)',('snakeReviewCatalogV1','verified-v1',json.dumps(nodes),json.dumps(connections)))
            c.execute('INSERT INTO execution_entity VALUES (?,?,?,?,?,?,?)',('1','snakeReviewCatalogV1','verified-v1','running','2026-10-15',None,'2026-10-15'))
            with patch.object(w,'CATALOG_PIN_PATH',pin):
                self.assertEqual(w.activity_count(c,2000000000),0)
                c.execute('UPDATE execution_entity SET workflowVersionId=?',('unknown-version',));self.assertEqual(w.activity_count(c,2000000000),1)
                c.execute('UPDATE execution_entity SET workflowVersionId=?',('verified-v1',));c.execute('UPDATE workflow_history SET nodes=?',(json.dumps([{'name':'Unexpected changed nodes'}]),));self.assertEqual(w.activity_count(c,2000000000),1)
                c.execute('UPDATE execution_entity SET workflowId=?',('snakeRetentionCoordinatorV1',));self.assertEqual(w.activity_count(c,2000000000),1)
