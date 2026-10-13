"""Artwork propagation and owner-only exact-ID poster maintenance for reviews."""
import copy,importlib.util,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('poster_helpers',ROOT/'n8n/recommendations/patch.py')
h=importlib.util.module_from_spec(s);s.loader.exec_module(h)

def build(source):
    out=copy.deepcopy(source);by={w['id']:w for w in out};w=by['snakeMediaReviewsV1']
    nodes={n['name']:n for n in w['nodes']}
    old=nodes['Review Decision']['parameters']['jsCode']
    config=re.search(r'users:(.+?),owners:(\[.*?\]),channels:(\[.*?\])',old)
    if not config:raise ValueError('Unknown review authorization boundary')
    users,owners,channels=config.groups()
    policy=(ROOT/'n8n/media-reviews/policy.js').read_text(encoding='utf-8')
    auth=(ROOT/'n8n/polish/authorization.js').read_text(encoding='utf-8')
    prefix=policy+'\n'+auth+'\n'
    def code(name,body):return h.node(name,'code',{'jsCode':prefix+body})
    body=old.split('\nconst result=reviewOperation(',1)[1]
    if 'posterUrl:$input' not in body:body=body.replace('availability:$input.first().json.availability,','availability:$input.first().json.availability,posterUrl:$input.first().json.posterUrl,')
    nodes['Review Decision']['parameters']['jsCode']=prefix+'const result=reviewOperation('+body
    identity=code('Prepare Review Artwork Identity',
        'const body=$("Review Webhook").first().json.body;return [{json:{artworkIdentity:reviewArtworkIdentity({body,rows:$("Read Review Rows").all().map(x=>x.json),users:'+users+',owners:'+owners+'})}}];')
    request_id=nodes['Read Owned Review Requests']['parameters']['dataTableId']['value']
    reader=h.table('Read Review Artwork Requests',request_id,filters=[h.eq('source','discord'),h.eq('state','registered'),
        h.eq('mediaType',"={{ $json.artworkIdentity?.mediaType || '__none__' }}"),h.eq('externalId',"={{ $json.artworkIdentity?.externalId || '__none__' }}")])
    reader['parameters'].pop('limit',None);reader['parameters']['returnAll']=True
    selection='const b=$("Review Webhook").first().json.body;const users='+users+';const owners='+owners+';const p=b&&users.includes(b.userId)&&["resolve","open","vote"].includes(b.op)&&b.myRequestsId?reviewRequestSelection({body:b,menus:$("Read Owned Review Menu").all().map(x=>x.json),requests:$("Read Owned Review Requests").all().map(x=>x.json),channels:'+channels+'}):null;const target=reviewArtworkTarget({body:b,rows:$("Read Review Rows").all().map(x=>x.json),requests:$input.all().map(x=>x.json).concat($("Read Review Request").all().map(x=>x.json)),notices:$("Read Review Notice").all().map(x=>x.json),users,owners,channels:'+channels+'});return [{json:{statusActor:p?.statusActor||null,artworkTarget:target}}];'
    nodes['Prepare Review Availability']['parameters']['jsCode']=prefix+selection
    additions=[identity,reader,h.condition('Review Artwork Needed?',"!!$('Prepare Review Availability').first().json.artworkTarget"),
        code('Review Artwork Target',"return [{json:$('Prepare Review Availability').first().json.artworkTarget}];"),
        h.condition('Review Artwork Movie?',"$json.requests[0].mediaType==='movie'"),
        code('Review Artwork Snapshot',"return [{json:{availability:null,posterUrl:reviewArtworkPoster($('Review Artwork Target').first().json,$json)}}];")]
    status_nodes={n['name']:n for n in by['snakeStatusInspectV1']['nodes']}
    for kind in ['Movie','Series']:
        n=copy.deepcopy(status_nodes['Read Status '+kind]);n.update(id='review-artwork-'+kind.lower(),name='Read Review Artwork '+kind,alwaysOutputData=True,onError='continueRegularOutput')
        additions.append(n)
    for n in additions:
        if n['name'] in nodes:nodes[n['name']].update(n)
        else:w['nodes'].append(n)
    h.connect(w,'Read Owned Review Requests','Prepare Review Artwork Identity');h.connect(w,'Prepare Review Artwork Identity','Read Review Artwork Requests')
    h.connect(w,'Read Review Artwork Requests','Prepare Review Availability')
    for name in ['Read Review Availability','Review No Availability']:h.connect(w,name,'Review Artwork Needed?')
    h.connect(w,'Review Artwork Needed?','Review Artwork Target');h.connect(w,'Review Artwork Needed?','Review Decision',1)
    h.connect(w,'Review Artwork Target','Review Artwork Movie?');h.connect(w,'Review Artwork Movie?','Read Review Artwork Movie');h.connect(w,'Review Artwork Movie?','Read Review Artwork Series',1)
    for kind in ['Movie','Series']:h.connect(w,'Read Review Artwork '+kind,'Review Artwork Snapshot')
    h.connect(w,'Review Artwork Snapshot','Review Decision')
    for i,n in enumerate(w['nodes']):n['position']=[i%6*270,i//6*220]
    return out
