"""Guided request transport and read-only status copy; preserve private bindings."""
import copy,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
IDS=('0e67KTcphqxEKNsh','HXtTzVTrpNZMZVt3','snakeStatusV1','snakeStatusInspectV1')
def build(source):
 rows=copy.deepcopy(source);by={w['id']:w for w in rows}
 status=(ROOT/'n8n/status/policy.js').read_text(encoding='utf-8').strip()
 marker="if(typeof module!=='undefined')module.exports={command,select,describe};"
 for w in rows:
  if w['id'] not in IDS:continue
  for n in w['nodes']:
   code=n.get('parameters',{}).get('jsCode','')
   if marker in code:
    if code.count(marker)!=1:raise ValueError('Unknown status generation')
    start=code.index('// Read-only status projection. Never calculates or changes retention policy.')
    n['parameters']['jsCode']=code[:start]+status+'\n'+code.split(marker)[1].lstrip('\n')
 w=by['0e67KTcphqxEKNsh'];ns={n['name']:n for n in w['nodes']}
 binding=re.search(r'return prepare\(\$json,("[^"\n]+")\);',ns['Prepare Request']['parameters']['jsCode'])
 if not binding:raise ValueError('Missing Telegram username binding')
 manifest=json.loads((ROOT/'src/snake_media/command_menu.json').read_text(encoding='utf-8'))
 ns['Prepare Request']['parameters']['jsCode']='const SNAKE_COMMAND_MENU='+json.dumps(manifest)+';\n'+(ROOT/'n8n/telegram-commands/policy.js').read_text(encoding='utf-8')+'\nreturn prepare($json,'+binding[1]+');'
 def edge(n):return [{'node':n,'type':'main','index':0}]
 if 'Resolve Guided Reply' not in ns:
  resolve=copy.deepcopy(ns['Touch Authorized Help Menu']);resolve.update(id='guided-resolve-reply',name='Resolve Guided Reply',position=[450,-160])
  resolve['parameters'].update(operation='resolvePrompt',message="={{ $('On message').first().json.message || {} }}")
  prompt=copy.deepcopy(resolve);prompt.update(id='guided-request-prompt',name='Ask For Request Title',position=[1600,-800]);prompt['parameters']['operation']='prompt'
  gate=copy.deepcopy(ns['Telegram Command Reply?']);gate.update(id='guided-prompt-gate',name='Request Title Prompt?',position=[1300,-650])
  gate['parameters']['conditions']['conditions'][0]['leftValue']='={{ $json.requestPrompt===true }}'
  # Copied boolean gates use true operator, retaining their strict native validation.
  gate['parameters']['conditions']['conditions'][0]['operator']={'type':'boolean','operation':'true','singleValue':True}
  w['nodes'].extend([resolve,prompt,gate])
  w['connections']['Authorized User?']['main'][0]=edge(resolve['name'])
  w['connections'][resolve['name']]={'main':[edge('Touch Authorized Help Menu')]}
  w['connections']['Telegram Command Reply?']['main'][0]=edge(gate['name'])
  w['connections'][gate['name']]={'main':[edge(prompt['name']),edge('Telegram Command Reply')]}
 return rows
if __name__=='__main__':
 import sys
 Path(sys.argv[2]).write_text(json.dumps(build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))),indent=2)+'\n',encoding='utf-8')
