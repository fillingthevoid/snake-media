import ast
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / 'n8n/polish/build_authorization.py'


def builder():
    if not any(isinstance(node, ast.FunctionDef) and node.name == 'build' for node in ast.parse(SCRIPT.read_text()).body):
        return None
    spec = importlib.util.spec_from_file_location('authorization_builder', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture():
    def node(name, kind, parameters=None):
        return {'name': name, 'type': 'n8n-nodes-base.' + kind, 'parameters': parameters or {}}
    return [{'id': 'HXtTzVTrpNZMZVt3', 'name': 'Media Request - Discord', 'settings': {'executionTimeout': 600}, 'nodes': [
        node('Discord Webhook', 'webhook', {'path': 'discord', 'authentication': 'headerAuth'}),
        node('Respond to Discord', 'respondToWebhook'),
        node('Discord Access Settings', 'set', {'assignments': {'assignments': [{'name': 'allowedUserIds', 'value': '111, 333'}]}}),
        node('Validate Discord Request', 'code'),
        node('Read Discord Authorization', 'dataTable'),
        node('Resolve Discord Authorization', 'code')
    ], 'connections': {}}]


class BuilderTests(unittest.TestCase):
    def test_emitted_code_bootstraps_rows_and_checks_acknowledged_union(self):
        backend, discord = builder().build(fixture(), {'ADMIN_DISCORD_USER_IDS': '111, 222', 'ALLOWED_DISCORD_CHANNEL_IDS': '444, 555', 'ALLOWED_DISCORD_USER_IDS': '111, 888'}, 'exact-control')
        def run(workflow, name, rows, refs):
            code = next(n for n in workflow['nodes'] if n['name'] == name)['parameters']['jsCode']
            script = "const fs=require('fs'),vm=require('vm');const i=JSON.parse(fs.readFileSync(0,'utf8'));const out=vm.runInNewContext('(function(){'+i.code+'})()',{$input:{all:()=>i.rows.map(json=>({json}))},$:name=>({first:()=>({json:i.refs[name]})})});process.stdout.write(JSON.stringify(out));"
            result = subprocess.run(['node', '-e', script], input=json.dumps({'code': code, 'rows': rows, 'refs': refs}), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        rows = [{'key': 'global', 'owner': 'running'}, {'key': 'discord-users', 'owner': '333, 666'}]
        grants = run(backend, 'Validate Owner Grant', rows, {'Authorization Webhook': {'body': {'actor': '222', 'channel': '555', 'guild': '999', 'user': '777', 'users': ['111', '222', '777']}}})
        self.assertEqual([r['json']['key'] for r in grants], ['discord-user:111', 'discord-user:222', 'discord-user:333', 'discord-user:666', 'discord-user:777', 'discord-user:888'])
        saved = rows + [{'key': r['json']['key'], 'owner': r['json']['owner']} for r in grants] + [{'key': 'discord-user:555', 'owner': '555'}]
        ack = run(backend, 'Authorization Synchronized', saved, {'Validate Owner Grant': grants[0]['json']})
        self.assertEqual(ack, [{'json': {'version': 1, 'synchronized': True, 'users': ['111', '222', '333', '555', '666', '777', '888']}}])
        resolved = run(discord, 'Resolve Discord Authorization', saved, {'Discord Access Settings': {'allowedUserIds': '111, 333', 'otherSetting': 'preserved'}})
        self.assertEqual(resolved, [{'json': {'allowedUserIds': '111,222,333,555,666,777,888', 'otherSetting': 'preserved'}}])

    def test_spaced_configuration_and_append_only_native_writes(self):
        module = builder()
        self.assertIsNotNone(module, 'Builder must expose its real transformation for verification')
        backend, discord = module.build(fixture(), {'ADMIN_DISCORD_USER_IDS': '111, 222', 'ALLOWED_DISCORD_CHANNEL_IDS': '444, 555'}, 'exact-control')
        saves = [n for n in backend['nodes'] if n['type'] == 'n8n-nodes-base.dataTable' and n['parameters']['operation'] != 'get']
        self.assertEqual(len(saves), 1)
        values = saves[0]['parameters']['columns']['value']
        self.assertEqual(values, {'key': '={{ $json.key }}', 'owner': '={{ $json.owner }}'})
        self.assertEqual(saves[0]['parameters']['filters']['conditions'][0]['keyValue'], '={{ $json.key }}')
        for workflow in [backend, discord]:
            for node in workflow['nodes']:
                if node['type'] == 'n8n-nodes-base.dataTable':
                    self.assertEqual(node['parameters']['dataTableId'], {'__rl': True, 'mode': 'id', 'value': 'exact-control'})
        self.assertEqual(module.parse_id_csv('111, 222,111', 'users'), ['111', '222'])
        for value in ['111,', '0', '18446744073709551616', '111, bad']:
            with self.assertRaises(ValueError):
                module.parse_id_csv(value, 'users')

    def test_rebuild_replaces_existing_lookup_without_duplicate_nodes(self):
        module = builder()
        self.assertIsNotNone(module)
        source = fixture()
        backend, once = module.build(source, {'ADMIN_DISCORD_USER_IDS': '111', 'ALLOWED_DISCORD_CHANNEL_IDS': '444'}, 'exact-control')
        _, twice = module.build([once], {'ADMIN_DISCORD_USER_IDS': '111', 'ALLOWED_DISCORD_CHANNEL_IDS': '444'}, 'exact-control')
        for name in ['Read Discord Authorization', 'Resolve Discord Authorization']:
            self.assertEqual(sum(n['name'] == name for n in twice['nodes']), 1)
        self.assertEqual(once, twice)
        self.assertEqual(source, fixture())
        self.assertTrue(next(n for n in backend['nodes'] if n['name'] == 'Verify Saved Discord Users')['executeOnce'])


if __name__ == '__main__':
    unittest.main()
