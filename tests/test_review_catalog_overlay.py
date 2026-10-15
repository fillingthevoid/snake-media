import importlib.util,json,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class ReviewCatalogOverlayTests(unittest.TestCase):
    def test_catalog_is_independent_owned_read_only_service_with_conditional_writes(self):
        spec=importlib.util.spec_from_file_location('catalog_overlay',ROOT/'n8n/review-catalog/patch.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        before=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))
        after=m.build(before);self.assertEqual(after,m.build(after))
        by={w['id']:w for w in after};w=by['snakeReviewCatalogV1'];nodes={n['name']:n for n in w['nodes']}
        self.assertTrue(nodes['Catalog Webhook']['parameters']['authentication'])
        filters=nodes['Claim Catalog Lease']['parameters']['filters']['conditions']
        self.assertTrue({'id','claimId','contextJson','expiresAt'} <= {x['keyName'] for x in filters})
        self.assertNotIn('global',str(w['connections']))
        for name in ['Read Catalog Rows','Read Catalog Import Events','Read Catalog Sonarr','Read Catalog Storage Health']:
            self.assertTrue(nodes[name].get('executeOnce'),name)
        for node in w['nodes']:
            if node['type'].endswith('.httpRequest'):self.assertEqual(node['parameters']['method'],'GET')
            self.assertFalse(node['type'].endswith('.executeCommand'))
        old={x['id']:x for x in before}
        for item in after:
            if item['id'] in old and item['id']!='snakeMediaReviewsV1':self.assertEqual(item,old[item['id']])
        bodies=[n['parameters']['jsCode'] for x in after for n in x['nodes'] if n['type'].endswith('.code')]
        result=subprocess.run(['node','-e',"for(const s of JSON.parse(require('fs').readFileSync(0,'utf8')))new Function(s);"],input=json.dumps(bodies),capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
