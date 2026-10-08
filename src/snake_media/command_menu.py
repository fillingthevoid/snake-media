"""Shared read-only navigation text; media decisions remain in n8n."""
import json
from pathlib import Path

MENU = json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
NAVIGATION = frozenset({'help', 'request', 'expiry', 'recommend', 'status',
                        'serverstatus', 'extend', 'keep'})


def menu_text(section):
    if section not in MENU:
        raise ValueError('Unknown menu section')
    return MENU[section]['text']


def menu_choices(section):
    if section not in MENU:
        raise ValueError('Unknown menu section')
    return [dict(choice) for choice in MENU[section]['choices']]
