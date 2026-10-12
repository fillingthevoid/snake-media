"""Shared Help and per-account recommendation defaults; native media nodes stay intact."""
import copy,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
IDS=('snakeRecommendV1','HXtTzVTrpNZMZVt3','0e67KTcphqxEKNsh','snakeTelegramCardV1')
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
h=load('defaults_helpers','n8n/recommendations/patch.py')
menu=load('defaults_menu','n8n/menu-simplification/patch.py')

def build(source):
    rows=menu.build(source);by={w['id']:w for w in rows};w=by['snakeRecommendV1'];nodes={n['name']:n for n in w['nodes']}
    table_id=nodes['Store Recommendation Menu']['parameters']['dataTableId']['value']
    if 'Read Recommendation Settings' not in nodes:
        read=h.table('Read Recommendation Settings',table_id,filters=[h.eq('source','={{ $json.source }}'),h.eq('userId','={{ $json.userId }}'),h.eq('state','recommendation-settings'),h.eq('requestKey',"={{ 'recommend-settings:'+$json.source+':'+$json.userId }}")])
        read['parameters'].update(limit=1,orderBy=True,orderByColumn='id',orderByDirection='DESC');read['onError']='continueRegularOutput'
        prep=h.code('Prepare Recommendation Setting',"return [{json:{setting:preferenceRecord($json.row)}}];")
        columns=list(nodes['Store Recommendation Menu']['parameters']['columns']['value'])
        write=h.table('Store Recommendation Settings',table_id,'upsert',[h.eq(k,'={{ $json.setting.'+k+' }}') for k in ['source','userId','state','requestKey']],{k:'={{ $json.setting.'+k+' }}' for k in columns})
        write['onError']='continueRegularOutput'
        restore=h.code('Restore Recommendation Generation',"return [{json:$('Verify Recommendation Claim').first().json}];")
        w['nodes'].extend([read,prep,write,restore])
    nodes={n['name']:n for n in w['nodes']}
    # The menu input is reconstructed from its trusted adapter context, not the settings row.
    policy=(ROOT/'n8n/recommendations/policy.js').read_text(encoding='utf-8').rstrip()
    nodes['Prepare Recommendation Menu']['parameters']['jsCode']=policy+"\nreturn [{json:{record:record($('Recommendation Input').first().json,Date.now(),$input.all().map(x=>x.json))}}];"
    h.connect(w,'Recommendation Action?','Read Recommendation Settings',1)
    h.connect(w,'Read Recommendation Settings','Prepare Recommendation Menu')
    h.connect(w,'Generate Recommendations?','Prepare Recommendation Setting')
    h.connect(w,'Prepare Recommendation Setting','Store Recommendation Settings')
    h.connect(w,'Store Recommendation Settings','Restore Recommendation Generation')
    h.connect(w,'Restore Recommendation Generation','Recommendation Generation Context')
    cards={n['name']:n for n in by['snakeTelegramCardV1']['nodes']}
    body=cards['Shared Menu Data']['parameters']['jsCode']
    if '"more"' not in body:body=body.replace('["help","request"','["help","more","request"')
    cards['Shared Menu Data']['parameters']['jsCode']=body
    return menu.build(rows)

if __name__=='__main__':
    import sys
    source=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'));out=build(source)
    changed=[w for w,old in zip(out,source) if w!=old]
    for w in changed:
        for k in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:w.pop(k,None)
        w.update(active=False,pinData={})
    p=Path(sys.argv[2]);p.write_text(json.dumps(changed,indent=2),encoding='utf-8');p.chmod(0o600)
    print('Scoped Help and recommendation updates:',len(changed))
