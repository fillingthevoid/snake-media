"""Add Telegram routing to the existing shared health workflow."""
import copy,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).parent

def build(rows,parent,bot_username):
    w=copy.deepcopy(parent);discord=next(r for r in rows if r['name']=='Media Request - Discord')
    names=['Parse Server Health Command','Server Health Command?','Read Server Health','Normalize Health Reply']
    if any(n['name'] in names for n in w['nodes']):raise ValueError('Already patched')
    old=w['connections']['Telegram Command Reply?']['main'][1]
    if old!=[{'node':'Parse Status Command','type':'main','index':0}]:raise ValueError('Unknown command route')
    prepare=next(n for n in w['nodes'] if n['name']=='Prepare Request')
    prepare['parameters']['jsCode']=(ROOT/'policy.js').read_text(encoding='utf-8-sig')+'\nreturn prepare($json,'+json.dumps(bot_username)+');'
    for i,name in enumerate(names):
        n=copy.deepcopy(next(n for n in discord['nodes'] if n['name']==name));n['id']=str(uuid.uuid4());n['position']=[810+i*270,1250]
        if name=='Parse Server Health Command':n['parameters']['jsCode']="const p=$json;return [{json:{...p,serverHealthCommand:typeof p.text==='string'&&/^\\/?serverstatus\\s*$/i.test(p.text.trim())}}];"
        w['nodes'].append(n)
    def edge(name):return [{'node':name,'type':'main','index':0}]
    w['connections']['Telegram Command Reply?']['main'][1]=edge(names[0])
    w['connections'][names[0]]={'main':[edge(names[1])]}
    w['connections'][names[1]]={'main':[edge(names[2]),old]}
    w['connections'][names[2]]={'main':[edge(names[3])]}
    w['connections'][names[3]]={'main':[edge('Preserve Telegram Reply')]}
    for k in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:w.pop(k,None)
    w.update(active=False,pinData={})
    return w

if __name__=='__main__':
    rows=json.loads(Path(sys.argv[1]).read_text());parent=next(w for w in rows if w['name']=='Media Request - Telegram')
    out=Path(sys.argv[2]);out.write_text(json.dumps([build(rows,parent,sys.argv[3])],indent=2));out.chmod(0o600)
    print('Built Telegram server status route; shared health backend unchanged')
