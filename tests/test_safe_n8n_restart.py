import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('restart',Path(__file__).resolve().parents[1]/'tools/safe_n8n_restart.py')
restart=importlib.util.module_from_spec(spec);spec.loader.exec_module(restart)


class RestartGuardTests(unittest.TestCase):
    def test_idle_check_must_be_away_from_scan_boundary(self):
        self.assertTrue(restart.restart_ready('',0,100))
        for owner,activity,now in [('50',0,100),('',1,100),('',0,899),('',0,905),('',0,5)]:
            self.assertFalse(restart.restart_ready(owner,activity,now))
