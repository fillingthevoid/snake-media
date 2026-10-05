import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class WorkflowBundleTests(unittest.TestCase):
    def tool(self):
        spec=importlib.util.spec_from_file_location('workflow_bundle',ROOT/'tools/workflow_bundle.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_current_bundle_has_complete_workflow_references(self):
        rows=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text())
        self.assertEqual(self.tool().validate(rows),len(rows))

    def test_duplicate_ids_missing_edges_and_unknown_children_are_rejected(self):
        w={'id':'a','name':'Example','nodes':[{'id':'n','name':'Input','type':'n8n-nodes-base.code','parameters':{'jsCode':'return [];'}}], 'connections':{}}
        for rows in [[w,w], [dict(w,connections={'Input':{'main':[[{'node':'Missing'}]]}})],
                     [dict(w,nodes=w['nodes']+[{'id':'call','name':'Child','type':'n8n-nodes-base.executeWorkflow','parameters':{'workflowId':{'value':'unknown'}}}])]]:
            with self.assertRaises(ValueError):self.tool().validate(rows)

    def test_apply_efficiency_preserves_input_and_validates_output(self):
        tool=self.tool()
        rows=json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text())
        before=copy.deepcopy(rows)
        output=tool.apply_efficiency(rows)
        self.assertEqual(rows,before)
        self.assertEqual(tool.validate(output),len(rows))
