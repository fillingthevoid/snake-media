"""Keep optional artwork outages from blocking verified completion delivery."""
import copy,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SHARED_IDS={'0e67KTcphqxEKNsh','HXtTzVTrpNZMZVt3','snakeQueueCandidateV1','snakeStatusInspectV1','snakeProgressNoticeV1'}

def build(source):
    rows=copy.deepcopy(source)
    poster=next(line for line in (ROOT/'n8n/polish/presentation/policy.js').read_text(encoding='utf-8').splitlines() if line.startswith('function poster('))
    for w in rows:
        if w['id'] not in SHARED_IDS:continue
        for n in w['nodes']:
            if w['id']=='snakeQueueCandidateV1' and n['name'] in ('Read Completion Media','Read Completion Series'):
                n.update(alwaysOutputData=True,onError='continueRegularOutput')
            body=n['parameters'].get('jsCode','')
            if '// Media presentation metadata' in body:
                body,count=re.subn(r'^function poster\(media\)\{[^\n]*\}',lambda _:poster,body,flags=re.M)
                if count!=1:raise ValueError('Unknown presentation poster boundary')
                n['parameters']['jsCode']=body
    return rows
