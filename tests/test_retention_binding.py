import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('binding', Path(__file__).parents[1] / 'n8n/retention/bind_tables.py')
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)

class BindingTests(unittest.TestCase):
    def test_exact_binding_ignores_longer_names(self):
        workflows = [{'nodes': [{'parameters': {'dataTableId': {'mode': 'name', 'value': 'snake_media_requests'}}}]}]
        result = binding.bind_tables(workflows, [('snake_media_requests_test', 'wrong'), ('snake_media_requests', 'right')])
        self.assertEqual(result[0]['nodes'][0]['parameters']['dataTableId'], {'__rl': True, 'mode': 'id', 'value': 'right'})
        self.assertEqual(workflows[0]['nodes'][0]['parameters']['dataTableId']['mode'], 'name')

    def test_missing_or_duplicate_table_fails_before_deployment(self):
        workflows = [{'nodes': [{'parameters': {'dataTableId': {'mode': 'name', 'value': 'requests'}}}]}]
        for rows in [[], [('requests', 'a'), ('requests', 'b')]]:
            with self.assertRaises(ValueError):
                binding.bind_tables(workflows, rows)
