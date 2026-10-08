"""Open fresh expiry confirmations without consuming the original controls."""
import copy,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('persistent_helpers',ROOT/'n8n/persistent-menus/patch.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
CHANGED_IDS=('snakeMyRequestsV1','snakeNoticeRetentionPreviewV1','0e67KTcphqxEKNsh')


def build(source):
    rows=copy.deepcopy(source);by={w['id']:w for w in rows}
    marker="if(typeof module!=='undefined')module.exports={MY_ACTION,create,advance,card};"
    for n in by['snakeMyRequestsV1']['nodes']:
        p=n['parameters'];body=p.get('jsCode','')
        if marker in body:p['jsCode']=h.replace_policy(body,ROOT/'n8n/my-requests/policy.js',marker)
        if n['name']=='Accept Request Expiry':p['jsCode']="return [{json:{...$json,actionAccepted:true,preserveOriginalControls:true}}];"
    notice=next(n for n in by['snakeNoticeRetentionPreviewV1']['nodes'] if n['name']=='Notice Result')['parameters']
    if 'preserveOriginalControls:true' not in notice['jsCode']:
        anchor='...r,actionAccepted:true,'
        if anchor not in notice['jsCode']:raise ValueError('Unknown notice feedback')
        notice['jsCode']=notice['jsCode'].replace(anchor,'...r,actionAccepted:true,preserveOriginalControls:true,')
    gate=next(n for n in by['0e67KTcphqxEKNsh']['nodes'] if n['name']=='Owned Text Card Cleanup?')['parameters']['conditions']['conditions'][0]
    if '$json.preserveOriginalControls!==true' not in gate['leftValue']:
        anchor='$json.busy!==true'
        if anchor not in gate['leftValue']:raise ValueError('Unknown Telegram cleanup guard')
        gate['leftValue']=gate['leftValue'].replace(anchor,anchor+' && $json.preserveOriginalControls!==true')
    return rows


if __name__=='__main__':
    import sys
    Path(sys.argv[2]).write_text(json.dumps(build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))),ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
