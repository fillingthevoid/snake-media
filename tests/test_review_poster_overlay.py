import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class ReviewPosterOverlayTests(unittest.TestCase):
    def test_only_reviews_change_and_metadata_reads_preserve_private_bindings(self):
        s=importlib.util.spec_from_file_location('posters',ROOT/'n8n/review-posters/patch.py')
        m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
        source=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text())
        out=m.build(source);self.assertEqual(out,m.build(out))
        by={w['id']:w for w in out};before={w['id']:w for w in source}
        for wid in by:
            if wid!='snakeMediaReviewsV1':self.assertEqual(by[wid],before[wid])
        nodes={n['name']:n for n in by['snakeMediaReviewsV1']['nodes']}
        status={n['name']:n for n in before['snakeStatusInspectV1']['nodes']}
        for kind in ['Movie','Series']:
            self.assertEqual(nodes['Read Review Artwork '+kind]['parameters'],status['Read Status '+kind]['parameters'])
            self.assertEqual(nodes['Read Review Artwork '+kind].get('credentials'),status['Read Status '+kind].get('credentials'))
            self.assertEqual(nodes['Read Review Artwork '+kind]['onError'],'continueRegularOutput')
        conditions=nodes['Read Review Artwork Requests']['parameters']['filters']['conditions']
        self.assertEqual({x['keyName'] for x in conditions},{'source','state','externalId','mediaType'})
        self.assertEqual(by['snakeMediaReviewsV1']['connections']['Read Review Availability']['main'][0][0]['node'],'Review Artwork Needed?')
        self.assertEqual(by['snakeMediaReviewsV1']['connections']['Review Artwork Needed?']['main'][1][0]['node'],'Review Decision')
