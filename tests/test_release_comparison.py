import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('bundle', Path(__file__).resolve().parents[1] / 'tools/workflow_bundle.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class ReleaseComparisonTests(unittest.TestCase):
    def workflow(self):
        return [{'id': 'a', 'name': 'Request', 'nodes': [
            {'id': 'one', 'name': 'Input', 'type': 'n8n-nodes-base.code', 'typeVersion': 2,
             'position': [0, 0], 'parameters': {'jsCode': 'return [{json:{accepted:true}}];'},
             'credentials': {'telegramApi': {'id': 'private', 'name': 'Private'}}}],
            'connections': {}, 'settings': {}, 'active': True}]

    def test_runtime_code_changes_are_reported_without_values(self):
        left = self.workflow()
        right = copy.deepcopy(left)
        right[0]['nodes'][0]['parameters']['jsCode'] = 'VERY_PRIVATE_CONTENT'
        changes = tool.compare(left, right)
        self.assertEqual(changes, ['a.nodes.Input.parameters.jsCode'])
        self.assertNotIn('VERY_PRIVATE_CONTENT', str(changes))

    def test_layout_credentials_and_deployment_metadata_are_ignored(self):
        left = self.workflow()
        right = copy.deepcopy(left)
        right[0].update(active=False, versionId='new')
        right[0]['nodes'][0].update(position=[999, 400], id='different',
                                  credentials={'telegramApi': {'id': 'another', 'name': 'Other'}})
        self.assertEqual(tool.compare(left, right), [])

    def test_missing_node_edges_type_and_credential_requirement_are_detected(self):
        left = self.workflow()
        for mutation, expected in [
            (lambda w: w[0]['nodes'][0].update(type='other'), 'a.nodes.Input.type'),
            (lambda w: w[0]['nodes'][0].update(credentials={}), 'a.nodes.Input.credentials.telegramApi'),
            (lambda w: w[0].update(nodes=[]), 'a.nodes.Input'),
            (lambda w: w[0].update(connections={'Input': {'main': [[{'node': 'Input', 'type': 'main', 'index': 0}]]}}), 'a.connections.Input')]:
            right = copy.deepcopy(left)
            mutation(right)
            self.assertIn(expected, tool.compare(left, right))

    def test_installation_bindings_do_not_hide_expressions_or_media_policy(self):
        left = self.workflow()
        left[0]['nodes'][0]['parameters'].update(url='http://private:5678/api', dataTableId={'value':'native-one','mode':'id'})
        right = copy.deepcopy(left)
        right[0]['nodes'][0]['parameters'].update(url='http://another:5678/api', dataTableId={'value':'native-two','mode':'id'})
        self.assertEqual(tool.compare(left, right), [])
        right[0]['nodes'][0]['parameters']['url'] = '={{ $json.arbitraryUrl }}'
        self.assertEqual(tool.compare(left, right), ['a.nodes.Input.parameters.url'])
