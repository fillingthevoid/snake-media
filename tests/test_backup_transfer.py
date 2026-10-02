import importlib.util
from pathlib import Path
import tempfile
import unittest


class BackupTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'tools/backup_serve.py'
        spec = importlib.util.spec_from_file_location('backup_serve', path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_only_completed_archives_are_listed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = 'snake-stack-20261002T000000Z.tar.gz.age'
            (root / name).write_bytes(b'encrypted')
            self.assertEqual(self.module.completed(root), [])
            (root / (name + '.sha256')).write_text('a' * 64 + '  ' + name)
            self.assertEqual(self.module.completed(root)[0]['name'], name)

    def test_path_traversal_and_private_key_requests_are_rejected(self):
        for command in ['get ../../identity.txt', 'get identity.txt', 'get /etc/passwd', 'list; cat /etc/passwd', 'get snake-stack-20261002T000000Z.tar.gz.age extra']:
            with self.assertRaises(ValueError):
                self.module.parse_command(command)
        self.assertEqual(self.module.parse_command('list'), ('list', None))
