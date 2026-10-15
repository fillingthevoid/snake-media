import copy,importlib.util,json,sqlite3,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pin_catalog',ROOT/'tools/pin_review_catalog.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class PinReviewCatalogTests(unittest.TestCase):
    def test_rejects_catalog_with_error_workflow_and_never_replaces_pin(self):
        expected={'id':'snakeReviewCatalogV1','nodes':[{'name':'Read Catalog Rows','type':'n8n-nodes-base.dataTable','parameters':{'operation':'get','dataTableId':{'value':'pending'}}}],'connections':{},'settings':{'errorWorkflow':'unexpected-side-effect'}}
        with sqlite3.connect(':memory:') as c,tempfile.TemporaryDirectory() as folder:
            c.executescript('CREATE TABLE workflow_entity(id TEXT,activeVersionId TEXT,settings TEXT);CREATE TABLE workflow_history(workflowId TEXT,versionId TEXT,nodes TEXT,connections TEXT);')
            c.execute('INSERT INTO workflow_entity VALUES (?,?,?)',('snakeReviewCatalogV1','v1',json.dumps(expected['settings'])))
            c.execute('INSERT INTO workflow_history VALUES (?,?,?,?)',('snakeReviewCatalogV1','v1',json.dumps(expected['nodes']),'{}'))
            output=Path(folder)/'pin.json';output.write_text('original')
            with self.assertRaises(ValueError):m.verify_and_pin(c,[expected],output)
            self.assertEqual(output.read_text(),'original')

    def test_pin_requires_exact_publication_and_reads_database_only(self):
        expected={'id':'snakeReviewCatalogV1','nodes':[{'name':'Read Catalog Rows','type':'n8n-nodes-base.dataTable','parameters':{'operation':'get','dataTableId':{'value':'pending'}}}],'connections':{},'settings':{}}
        with sqlite3.connect(':memory:') as c,tempfile.TemporaryDirectory() as folder:
            c.executescript('CREATE TABLE workflow_entity(id TEXT,activeVersionId TEXT,settings TEXT);CREATE TABLE workflow_history(workflowId TEXT,versionId TEXT,nodes TEXT,connections TEXT);')
            c.execute('INSERT INTO workflow_entity VALUES (?,?,?)',('snakeReviewCatalogV1','v1','{}'));c.execute('INSERT INTO workflow_history VALUES (?,?,?,?)',('snakeReviewCatalogV1','v1',json.dumps(expected['nodes']),'{}'))
            statements=[];c.set_trace_callback(statements.append)
            output=Path(folder)/'pin.json';pin=m.verify_and_pin(c,[expected],output)
            self.assertEqual(pin['versionId'],'v1');self.assertTrue(all(s.lstrip().upper().startswith('SELECT') for s in statements))
            drift=copy.deepcopy(expected);drift['nodes'][0]['parameters']['operation']='deleteRows'
            with self.assertRaises(ValueError):m.verify_and_pin(c,[drift],output)
            self.assertEqual(json.loads(output.read_text()),pin)
