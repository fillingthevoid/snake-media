"""Update Telegram callback cards without changing backend decisions or bindings."""
import copy
import json
from pathlib import Path
import sys


CALLBACK = """
// Presentation context comes from the authenticated Telegram update.
const callback=$('On message').first().json.callback_query;
if(callback)for(const item of items)Object.assign(item.json,{callbackMessage:callback.message,callbackData:callback.data,callbackId:callback.id});
return items;
"""


def build(source):
    rows = copy.deepcopy(source)
    by_id = {w['id']: w for w in rows}
    root = by_id['0e67KTcphqxEKNsh']
    node = next(n for n in root['nodes'] if n['name'] == 'Format Interactive Reply')
    code = node['parameters']['jsCode'].replace('else for(const item of items)item.json.requestMessageId=String(p.messageId);\n', '')
    node['parameters']['jsCode'] = code
    if '// Presentation context comes' not in code:
        marker = 'return [{json:{...r,ownerId:String(p.userId)'
        if marker not in code or not code.rstrip().endswith('}}}];'):
            raise ValueError('Unknown Telegram reply formatter')
        code = code.replace(marker, 'const items=[{json:{...r,ownerId:String(p.userId)', 1)
        node['parameters']['jsCode'] = code + CALLBACK
    # The editor owns the complete keyboard and registry transition. Pre-edit
    # cleanup would queue removal of the very same message after its edit.
    root['connections']['Preserve Telegram Reply'] = {'main': [[{'node': 'Restore Telegram Reply', 'type': 'main', 'index': 0}]]}
    card = by_id['snakeTelegramCardV1']
    if not any(n['name'] == 'Present Telegram Card' for n in card['nodes']):
        template = next(n for n in card['nodes'] if n['name'] == 'Send Shared Menu')
        sender = copy.deepcopy(template)
        sender.update(id='snake-telegram-present-card', name='Present Telegram Card', position=[440, -440])
        sender.pop('onError', None)
        sender['parameters'] = {'operation': 'presentCard', 'ownerId': '={{ $json.ownerId }}'}
        card['nodes'].append(sender)
    card['connections']['Validate Card'] = {'main': [[{'node': 'Present Telegram Card', 'type': 'main', 'index': 0}]]}
    return rows


if __name__ == '__main__':
    source = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    Path(sys.argv[2]).write_text(json.dumps(build(source), indent=2) + '\n', encoding='utf-8')
