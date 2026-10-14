"""Guard native comment-reference deletion and existing-post pointer updates."""
import copy,importlib.util,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('recovery_helpers',ROOT/'n8n/recommendations/patch.py')
h=importlib.util.module_from_spec(s);s.loader.exec_module(h)

def build(source):
    out=copy.deepcopy(source);w=next(w for w in out if w['id']=='snakeMediaReviewsV1')
    nodes={n['name']:n for n in w['nodes']}
    policy=(ROOT/'n8n/media-reviews/policy.js').read_text(encoding='utf-8').rstrip()
    for n in w['nodes']:
        p=n.get('parameters',{});body=p.get('jsCode','')
        if body.startswith('// Review decisions and storage belong to n8n'):
            body,count=re.subn(r"\A// Review decisions[\s\S]*?\nif\(typeof module!=='undefined'\)module.exports=\{[^\n]*\};",lambda _:policy,body,count=1)
            if count!=1:raise ValueError('Unknown review policy boundary')
            p['jsCode']=body
    table=nodes['Save Review Row']['parameters']['dataTableId']['value']
    guard=lambda key:[h.eq('id','={{ $json.'+key+'.id }}'),h.eq('requestKey','={{ $json.'+key+'.requestKey }}'),
        h.eq('contextJson','={{ $json.'+key+'.contextJson }}'),h.eq('source','discord'),h.eq('state','review')]
    delete=h.table('Delete Confirmed Review Comment',table,'deleteRows',guard('deleteComment'))
    verify=h.table('Verify Deleted Review Comment',table,filters=[h.eq('requestKey',"={{ $('Review Decision').first().json.deleteComment.requestKey }}"),h.eq('source','discord'),h.eq('state','review')])
    verify['parameters'].pop('limit',None);verify['parameters']['returnAll']=True
    removed=h.node('Review Comment Deletion Verified','code',{'jsCode':"const d=$('Review Decision').first().json;if($input.all().some(x=>x.json.requestKey===d.deleteComment.requestKey))throw Error('comment_reference_changed');return [{json:d.reply}];"})
    update=copy.deepcopy(nodes['Save Review Row']);update.update(id='review-update-existing-post',name='Update Existing Review Post')
    update['parameters']['operation']='update';update['parameters']['filters']={'conditions':guard('postOriginal')}
    additions=[h.condition('Review Comment Delete?','!!$json.deleteComment'),delete,verify,removed,
        h.condition('Review Existing Post?','!!$json.postOriginal'),update]
    for n in additions:
        if n['name'] in nodes:nodes[n['name']].update(n)
        else:w['nodes'].append(n)
    h.connect(w,'Review Decision','Review Comment Delete?');h.connect(w,'Review Comment Delete?','Delete Confirmed Review Comment')
    h.connect(w,'Review Comment Delete?','Review Write?',1);h.connect(w,'Delete Confirmed Review Comment','Verify Deleted Review Comment')
    h.connect(w,'Verify Deleted Review Comment','Review Comment Deletion Verified');h.connect(w,'Review Comment Deletion Verified','Review Response')
    h.connect(w,'Review Menu Write?','Review Existing Post?',1);h.connect(w,'Review Existing Post?','Update Existing Review Post')
    h.connect(w,'Review Existing Post?','Save Review Row',1);h.connect(w,'Update Existing Review Post','Verify Review Row')
    for i,n in enumerate(w['nodes']):n['position']=[i%6*270,i//6*220]
    return out
