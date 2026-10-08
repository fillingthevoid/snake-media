"""Targeted Telegram entrypoint overlay; private credential bindings preserved."""
import copy,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).parent

def build(source,bot_username):
    if not bot_username or not all(c.isalnum() or c=='_' for c in bot_username):raise ValueError('Invalid bot username')
    w=copy.deepcopy(source)
    def node(name):return next(n for n in w['nodes'] if n['name']==name)
    node('Prepare Request')['parameters']['jsCode']='const SNAKE_COMMAND_MENU='+json.dumps(json.loads((ROOT.parent.parent/'src/snake_media/command_menu.json').read_text(encoding='utf-8')))+';\n'+(ROOT/'policy.js').read_text(encoding='utf-8-sig')+'\nreturn prepare($json,'+json.dumps(bot_username)+');'
    existing=w['connections']['Confirmation Callback?']['main'][1]
    if existing!=[{'node':'Parse Status Command','type':'main','index':0}]:raise ValueError('Unknown Telegram command route')
    template=copy.deepcopy(node('Status Command?'));template.update(id=str(uuid.uuid4()),name='Telegram Command Reply?',position=[1080,250])
    template['parameters']['conditions']['conditions'][0]['leftValue']="={{ typeof $json.commandReply==='string' }}"
    reply={'id':str(uuid.uuid4()),'name':'Telegram Command Reply','type':'n8n-nodes-base.code','typeVersion':2,'position':[1350,250],
           'parameters':{'jsCode':"return [{json:{version:1,status:'notice',text:$json.commandReply}}];"}}
    w['nodes'].extend([template,reply])
    def edge(name):return [{'node':name,'type':'main','index':0}]
    w['connections']['Confirmation Callback?']['main'][1]=edge(template['name'])
    w['connections'][template['name']]={'main':[edge(reply['name']),existing]}
    w['connections'][reply['name']]={'main':[edge('Preserve Telegram Reply')]}
    for k in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:w.pop(k,None)
    w.update(active=False,pinData={})
    return w

if __name__=='__main__':
    source=json.loads(Path(sys.argv[1]).read_text());w=next(w for w in source if w['name']=='Media Request - Telegram')
    out=Path(sys.argv[2]);out.write_text(json.dumps([build(w,sys.argv[3])],indent=2));out.chmod(0o600)
    print('Built Telegram command overlay; credentials preserved')
