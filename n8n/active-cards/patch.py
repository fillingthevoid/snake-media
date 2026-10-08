"""Remember original request cards and edit them before notification fallback."""
import copy, importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('active_helpers',ROOT/'n8n/recommendations/patch.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
CHANGED_IDS=('snakePreviewMediaV1','snakeTelegramCardV1','snakeTelegramNoticeSendV1')


def build(source):
    rows=copy.deepcopy(source);by={w['id']:w for w in rows}
    delivery=by['snakeTelegramNoticeSendV1']
    if any(n['name']=='Update Original Telegram Request' for n in delivery['nodes']):return rows
    preview=next(n for n in by['snakePreviewMediaV1']['nodes'] if n['name']=='Render Preview')
    old=preview['parameters']['jsCode']
    preview['parameters']['jsCode']="// Original request transport reference\nconst renderOriginal=()=>{\n"+old+"\n};\nconst output=renderOriginal();let context={};try{context=JSON.parse($json.contextJson||'{}');}catch{}\nfor(const item of output)if(item.json.status==='confirmation'&&/^[1-9][0-9]{0,19}$/.test(String(context.messageId||'')))item.json.requestMessageId=String(context.messageId);return output;"
    for n in by['snakeTelegramCardV1']['nodes']:
        if n['type']=='CUSTOM.snakeTelegramControls' and n['parameters'].get('operation')=='remember':
            n['parameters']['requestMessageId']="={{ $('Card Input').first().json.requestMessageId || '' }}"
    update=copy.deepcopy(next(n for n in delivery['nodes'] if n['name']=='Remember Telegram Completion Card'))
    update.update(id='active-update-original-telegram-request',name='Update Original Telegram Request',position=[520,600])
    update['parameters'].update(operation='update',requestMessageId="={{ String(JSON.parse($('Notice Input').first().json.payloadJson).messageId || '') }}")
    # Errors must stay unacknowledged for the next scheduled delivery attempt.
    update.pop('onError',None)
    delivery['nodes'] += [update,h.condition('Original Telegram Card Updated?','$json.originalCardUpdated===true'),
        h.condition('Original Telegram Card Retry?','$json.originalCardRetry===true'),
        h.node('Retry Original Telegram Card','code',{'jsCode':"throw new Error('Original Telegram card edit temporarily unavailable');"}),
        h.node('Restore Original Completion Metadata','code',{'jsCode':"return [{json:$('Completion Card Metadata').first().json}];"})]
    h.connect(delivery,'Completion Card Metadata','Update Original Telegram Request')
    h.connect(delivery,'Update Original Telegram Request','Original Telegram Card Updated?')
    h.connect(delivery,'Original Telegram Card Updated?','Remember Telegram Completion Card')
    h.connect(delivery,'Original Telegram Card Updated?','Original Telegram Card Retry?',1)
    h.connect(delivery,'Original Telegram Card Retry?','Retry Original Telegram Card')
    h.connect(delivery,'Original Telegram Card Retry?','Restore Original Completion Metadata',1)
    h.connect(delivery,'Restore Original Completion Metadata','Completion Retention Controls?')
    return rows


if __name__=='__main__':
    import sys
    Path(sys.argv[2]).write_text(json.dumps(build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))),indent=2)+'\n',encoding='utf-8')
