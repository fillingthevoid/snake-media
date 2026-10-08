"""Refresh shared menus and recommendation policies without replacing bindings."""
import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IDS = ('snakeRecommendV1', 'HXtTzVTrpNZMZVt3', '0e67KTcphqxEKNsh', 'snakeTelegramCardV1')
MARKER = "if(typeof module!=='undefined')module.exports={GENRES,RECACTION,history,suggestions,verified,providerItem,librarySearchTitle,availability,record,transition,generation,completed,card};"


def build(source):
    rows = copy.deepcopy(source)
    workflows = {w['id']: w for w in rows}
    policy = (ROOT/'n8n/recommendations/policy.js').read_text(encoding='utf-8')
    for wid in IDS:
        for node in workflows[wid]['nodes']:
            body = node['parameters'].get('jsCode', '')
            if MARKER in body:
                if body.count(MARKER) != 1:
                    raise ValueError('Unknown embedded recommendation generation')
                tail = body.split(MARKER)[1].replace('r.type,r.genre);', 'r.type,r.genre,r.seen||[]);')
                node['parameters']['jsCode'] = policy.rstrip() + '\n' + tail.lstrip('\n')
            conditions = node['parameters'].get('conditions', {}).get('conditions', [])
            for condition in conditions:
                if node['name']=='Recommendation Callback?':
                    condition['leftValue'] = condition['leftValue'].replace('|choose|cancel)', '|choose|cancel|change|more)')
    telegram = workflows['0e67KTcphqxEKNsh']
    nodes = {n['name']: n for n in telegram['nodes']}
    old = nodes['Prepare Request']['parameters']['jsCode']
    username = re.search(r'return prepare\(\$json,("[^"\n]+")\);', old)
    if not username:
        raise ValueError('Telegram username binding missing')
    manifest = json.loads((ROOT/'src/snake_media/command_menu.json').read_text(encoding='utf-8'))
    nodes['Prepare Request']['parameters']['jsCode'] = (
        'const SNAKE_COMMAND_MENU='+json.dumps(manifest)+';\n'+
        (ROOT/'n8n/telegram-commands/policy.js').read_text(encoding='utf-8')+
        '\nreturn prepare($json,'+username[1]+');')
    nodes['Telegram Command Reply']['parameters']['jsCode'] = (
        'return [{json:{version:1,status:"notice",text:$json.commandReply,'
        'menuChoices:$json.menuChoices||[]}}];')
    cards = workflows['snakeTelegramCardV1']
    cn = {n['name']: n for n in cards['nodes']}
    # Three-column recommendation genres; preserve normal confirmations and links.
    body = cn['Recommendation Card Data']['parameters']['jsCode']
    start = 'const r=$json,rows=(r.keyboard?.rows||[]).slice();'
    replacement = ('const r=$json;let rows=(r.keyboard?.rows||[]).slice();'
        'if(r.choices?.some(c=>/^rec_genre_/.test(c.action))){'
        'const genres=r.choices.filter(c=>/^rec_genre_/.test(c.action));rows=[];'
        'for(let i=0;i<genres.length;i+=3)rows.push({row:{buttons:genres.slice(i,i+3).map(c=>'
        '({text:c.label,additionalFields:{callback_data:"snake:"+r.pendingId+":"+c.action}}))}});'
        'rows.push({row:{buttons:[{text:"Cancel",additionalFields:{callback_data:"snake:"+r.pendingId+":rec_cancel"}}]}});}')
    if start in body:
        cn['Recommendation Card Data']['parameters']['jsCode'] = body.replace(start, replacement)
    elif replacement not in body:
        raise ValueError('Unknown recommendation keyboard generation')
    if 'Shared Menu?' not in cn:
        gate = copy.deepcopy(cn['Recommendation Card?'])
        gate.update(id='shared-menu-gate', name='Shared Menu?')
        gate['parameters']['conditions']['conditions'][0]['leftValue'] = '={{ Array.isArray($json.menuChoices) && $json.menuChoices.length>0 }}'
        prep = copy.deepcopy(cn['Recommendation Card Data'])
        prep.update(id='shared-menu-data', name='Shared Menu Data')
        prep['parameters']['jsCode'] = ('const allowed=new Set(["help","request","expiry","recommend","status","serverstatus","extend","keep"]);'
            'const cs=$json.menuChoices;if(!Array.isArray(cs)||cs.length>8||cs.some(c=>!allowed.has(c.action)||typeof c.label!=="string"||c.label.length>80))throw Error("Invalid menu");'
            'const rows=[];for(let i=0;i<cs.length;i+=3)rows.push({row:{buttons:cs.slice(i,i+3).map(c=>({text:c.label,additionalFields:{callback_data:"snake_menu:"+c.action}}))}});'
            'return [{json:{...$json,keyboard:{rows}}}];')
        send = copy.deepcopy(cn['Send Recommendation Text'])
        send.update(id='shared-menu-send', name='Send Shared Menu')
        send['parameters']['inlineKeyboard']['rows'] = "={{ $('Shared Menu Data').first().json.keyboard.rows }}"
        cards['nodes'] += [gate, prep, send]
        def edge(name):
            return [{'node': name, 'type': 'main', 'index': 0}]
        old_route = cards['connections']['Validate Card']['main'][0]
        cards['connections']['Validate Card']['main'][0] = edge('Shared Menu?')
        cards['connections']['Shared Menu?'] = {'main': [edge('Shared Menu Data'), old_route]}
        cards['connections']['Shared Menu Data'] = {'main': [edge('Send Shared Menu')]}
    return rows


if __name__=='__main__':
    import sys
    source=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    Path(sys.argv[2]).write_text(json.dumps(build(source),indent=2)+'\n',encoding='utf-8')
