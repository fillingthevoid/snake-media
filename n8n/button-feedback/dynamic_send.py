"""Avoid n8n fixedCollection normalization stripping expression-driven rows."""
import copy


def build(source):
    rows = copy.deepcopy(source)
    for workflow in rows:
        if workflow['id'] != 'snakeTelegramCardV1':
            continue
        for node in workflow['nodes']:
            keyboard = node['parameters'].get('inlineKeyboard', {})
            expression = keyboard.get('rows') if isinstance(keyboard, dict) else None
            if node['type'] != 'n8n-nodes-base.telegram' or not isinstance(expression, str):
                continue
            if node['parameters'].get('operation') not in ('sendPhoto', 'sendMessage'):
                raise ValueError('Unexpected dynamic Telegram operation')
            node['type'] = 'CUSTOM.snakeTelegramControls'
            mode = 'photo' if node['parameters']['operation'] == 'sendPhoto' else 'text'
            node['typeVersion'] = 1
            node['parameters'] = {'operation': 'sendCard', 'sendMode': mode}
    return rows


if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    source = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    Path(sys.argv[2]).write_text(json.dumps(build(source), indent=2)+'\n', encoding='utf-8')
