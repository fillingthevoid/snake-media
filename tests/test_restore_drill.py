import importlib.util
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

spec = importlib.util.spec_from_file_location('restore_drill', Path(__file__).resolve().parents[1] / 'tools/restore_drill.py')


class RestoreDrillTests(unittest.TestCase):
    def tool(self):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_plan_is_network_isolated_and_mounts_only_the_restored_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sonarr').mkdir()
            args = self.tool().container_command('sonarr', 'sha256:example', root, 'drill-example')
            self.assertIn('none', args)
            self.assertEqual(args[args.index('--network') + 1], 'none')
            self.assertNotIn('-p', args)
            self.assertNotIn('--privileged', args)
            self.assertEqual(args[args.index('--mount') + 1], f'type=bind,src={(root / "sonarr").resolve()},dst=/config')
            self.assertNotIn('/mnt/media', ' '.join(args))

    def test_only_known_applications_and_disposable_names_are_allowed(self):
        tool = self.tool()
        for app, name in [('jellyfin', 'drill-example'), ('sonarr', 'sonarr'), ('n8n', '../drill')]:
            with self.assertRaises(ValueError):
                tool.container_command(app, 'sha256:example', Path('/tmp'), name)
