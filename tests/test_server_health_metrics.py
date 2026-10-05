import importlib.util,unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
spec=importlib.util.spec_from_file_location('metrics',Path(__file__).resolve().parents[1]/'tools/server_health.py')
health=importlib.util.module_from_spec(spec);spec.loader.exec_module(health)
class Metrics(unittest.TestCase):
    def test_optional_gpu_fields_are_independent_of_base_usage(self):
        result=health.parse_gpu('NVIDIA GeForce GTX 1070, 12, 1024, 8192, 36, 20, 40')
        self.assertEqual(result['temperatureC'],36)
        self.assertEqual(result['encoderPercent'],20)
        self.assertEqual(result['decoderPercent'],40)
        result=health.parse_gpu('GTX 1070, 0, 0, 8192, N/A, [Not Supported], 101')
        self.assertTrue(result['available']);self.assertEqual(result['utilizationPercent'],0)
        for key in ('temperatureC','encoderPercent','decoderPercent'):self.assertIsNone(result[key])
    def test_gpu_parses_utilization_and_memory_and_rejects_unknown(self):
        self.assertEqual(health.parse_gpu('NVIDIA GeForce GTX 1070, 12, 1024, 8192')['utilizationPercent'],12)
        for output in ['GTX 1070, N/A, 1024, 8192','GTX 1070, 101, 1024, 8192','GTX 1070, 0, 8193, 8192']:
            with self.assertRaises(ValueError):health.parse_gpu(output)
    def test_upload_uses_byte_delta_elapsed_time_and_rejects_resets(self):
        self.assertEqual(health.upload_rate(1000,2001000,2),8)
        self.assertEqual(health.upload_rate(1000,1000,2),0)
        for before,after,elapsed in [(2000,1000,2),(0,1000,0),(0,1000,float('nan'))]:
            with self.assertRaises(ValueError):health.upload_rate(before,after,elapsed)
    def test_failed_optional_probe_does_not_report_zero_usage(self):
        with patch.object(health.subprocess,'check_output',side_effect=FileNotFoundError):self.assertFalse(health.gpu_probe()['available'])
