"""Targeted queue recovery overlay; preserves private bindings and unrelated nodes."""
import copy
import json
import os
from pathlib import Path

VALIDATE = """const b=$input.first().json.body;
if(b?.action==='poll'){
 const keys=b.excludeNotificationKeys||[],cursor=b.afterNotificationId??null;
 if(!Array.isArray(keys)||keys.length>1000||keys.some(k=>typeof k!=='string'||!k.length||k.length>300))throw Error('Invalid queue exclusions');
 if(cursor!==null&&(typeof cursor!=='string'||!(/^[1-9][0-9]{0,19}$/).test(cursor)))throw Error('Invalid queue cursor');
 return [{json:{action:'poll',excludeNotificationKeys:keys,afterNotificationId:cursor}}];
}
if(b?.action==='ack'&&typeof b.notificationKey==='string'&&b.notificationKey.startsWith('discord:')&&b.notificationKey.length<=300){
 if(b.receiptRecovered===true&&b.messageId===undefined)return [{json:{action:'ack',notificationKey:b.notificationKey,receiptRecovered:true}}];
 if(b.receiptRecovered===undefined&&typeof b.messageId==='string'&&/^[1-9][0-9]{0,19}$/.test(b.messageId))return [{json:{action:'ack',notificationKey:b.notificationKey,messageId:b.messageId}}];
}
throw Error('Invalid queue action');"""


def build(workflows):
    result = copy.deepcopy(workflows)
    queue = next(w for w in result if w['id'] == 'snakeNotificationQueueV1')
    nodes = {n['name']: n for n in queue['nodes']}
    nodes['Validate Queue Action']['parameters']['jsCode'] = VALIDATE
    policy = Path(__file__).with_name('policy.js').read_text(encoding='utf-8')
    nodes['Queue Batch']['parameters']['jsCode'] = policy + """
const action=$('Validate Queue Action').first().json;
return [{json:queueBatch($input.all().map(x=>x.json),action.excludeNotificationKeys||[],action.afterNotificationId??null)}];"""
    nodes['Acknowledge Discord Notice']['parameters']['columns']['value']['deliveredMessageId'] = "={{ $json.messageId ?? '' }}"
    collector = nodes['Collect Preferred Queue']['parameters']
    old = "return [{json:{version:1,notifications:$input.all().map(x=>x.json)}}];"
    new = "return [{json:{version:1,notifications:$input.all().map(x=>x.json),nextCursor:$('Queue Batch').first().json.nextCursor??null}}];"
    if old not in collector['jsCode'] and new not in collector['jsCode']:
        raise ValueError('Unknown queue collection code; no export prepared')
    collector['jsCode'] = collector['jsCode'].replace(old, new)
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('Use a separate output file to preserve the original export')
    result = build(json.loads(args.input.read_text(encoding='utf-8')))
    with args.output.open('x', encoding='utf-8') as stream:
        os.chmod(args.output, 0o600)
        stream.write(json.dumps(result, ensure_ascii=True, indent=2) + '\n')
