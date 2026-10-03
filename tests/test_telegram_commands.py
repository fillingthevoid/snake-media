import unittest,json,importlib.util
from pathlib import Path

class Overlay(unittest.TestCase):
    def test_only_preparation_and_authorized_noncallback_route_change(self):
        root=Path(__file__).resolve().parents[1]
        source=root/'config-templates/n8n-current-media-workflows.json'
        if not source.exists():source=root.parent/'snake-media-public/config-templates/n8n-current-media-workflows.json'
        rows=json.loads(source.read_text());original=next(w for w in rows if w['name']=='Media Request - Telegram')
        spec=importlib.util.spec_from_file_location('telegram_build',root/'n8n/telegram-commands/build.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        original['nodes']=[n for n in original['nodes'] if n['name'] not in ['Telegram Command Reply?','Telegram Command Reply']]
        original['connections']['Confirmation Callback?']['main'][1]=[{'node':'Parse Status Command','type':'main','index':0}]
        for name in ['Telegram Command Reply?','Telegram Command Reply']:original['connections'].pop(name,None)
        changed=module.build(original,'SnakeBot')
        self.assertEqual(changed['connections']['Authorized User?'],original['connections']['Authorized User?'])
        self.assertEqual(changed['connections']['Confirmation Callback?']['main'][0],original['connections']['Confirmation Callback?']['main'][0])
        self.assertEqual(changed['connections']['Confirmation Callback?']['main'][1][0]['node'],'Telegram Command Reply?')
        self.assertEqual(changed['connections']['Telegram Command Reply?']['main'][1][0]['node'],'Parse Status Command')
        lookup={n['name']:n for n in changed['nodes']}
        for node in original['nodes']:
            if node['name']!='Prepare Request':self.assertEqual(node,lookup[node['name']])
        self.assertEqual(lookup['Telegram Command Reply?']['parameters']['conditions']['conditions'][0]['leftValue'],"={{ typeof $json.commandReply==='string' }}")
        reply=lookup['Telegram Command Reply']['parameters']['jsCode']
        self.assertNotIn('http',reply);self.assertNotIn('OpenAI',reply)
