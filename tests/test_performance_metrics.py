import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import performance_metrics as metrics


class PerformanceTests(unittest.TestCase):
    def test_cpu_excludes_guest_double_counting_and_idle_wait(self):
        before = metrics.cpu_counters('cpu 100 0 50 800 50 0 0 0 20 0\ncpu0 1 2 3')
        after = metrics.cpu_counters('cpu 120 0 60 860 60 0 0 0 30 0')
        self.assertEqual(metrics.cpu_usage(before, after), 30)
        self.assertEqual(metrics.cpu_usage(after, (120, 0, 60, 960, 60, 0, 0, 0)), 0)
        for bad in ['cpu x 0 0 0 0 0 0 0', 'cpu 1 2 3', 'cpu0 1 2 3 4 5 6 7 8']:
            with self.assertRaises(ValueError):
                metrics.cpu_counters(bad)
        with self.assertRaises(ValueError):
            metrics.cpu_usage(after, before)

    def test_weighted_average_warmup_resets_interface_changes_and_stale_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stat = root / 'stat'
            net = root / 'net'
            interface = net / 'eth0'
            (interface / 'statistics').mkdir(parents=True)
            (interface / 'device').mkdir()
            (interface / 'operstate').write_text('up')
            # A virtual interface must never double-count physical traffic.
            (net / 'docker0/statistics').mkdir(parents=True)
            (net / 'docker0/operstate').write_text('up')
            (net / 'docker0/statistics/tx_bytes').write_text('999999999')
            sampler = metrics.PerformanceSampler(stat, net)
            def tick(now, sent, busy, idle):
                stat.write_text(f'cpu {busy} 0 0 {idle} 0 0 0 0 0 0')
                (interface / 'statistics/tx_bytes').write_text(str(sent))
                sampler.tick(now)
                return sampler.snapshot(now)
            self.assertFalse(tick(0, 0, 0, 0)['network']['available'])
            reading = tick(2, 2000000, 20, 80)
            self.assertEqual(reading['cpu']['usagePercent'], 20)
            self.assertEqual(reading['network']['uploadMbps'], 8)
            self.assertIsNone(reading['network']['uploadAverageMbps'])
            for second in range(4,62,2):
                reading = tick(second, int(2000000+(second-2)*28000000/58), 20+second, 80+second*4)
            self.assertEqual(reading['network']['uploadAverageMbps'], 4)
            self.assertEqual(reading['network']['averageSeconds'], 60)
            self.assertFalse(sampler.snapshot(67)['network']['available'])
            self.assertFalse(tick(62, 1, 40, 280)['network']['available'])
            reading = tick(64, 1, 50, 380)
            self.assertEqual(reading['network']['uploadMbps'], 0)
            self.assertIsNone(reading['network']['uploadAverageMbps'])
            (interface / 'operstate').write_text('down')
            self.assertFalse(tick(66, 1, 60, 480)['network']['available'])
            (interface / 'operstate').write_text('up')
            self.assertFalse(tick(68, 2, 70, 580)['network']['available'])
            self.assertIsNone(tick(70, 2, 80, 680)['network']['uploadAverageMbps'])

    def test_failed_cpu_read_does_not_hide_network_or_reuse_old_cpu(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); stat = root / 'stat'; net = root / 'net'
            interface = net / 'eth0'
            (interface / 'statistics').mkdir(parents=True)
            (interface / 'device').mkdir()
            (interface / 'operstate').write_text('up')
            (interface / 'statistics/tx_bytes').write_text('0')
            stat.write_text('cpu 0 0 0 0 0 0 0 0')
            sampler = metrics.PerformanceSampler(stat, net); sampler.tick(0)
            stat.write_text('bad'); sampler.tick(2)
            value = sampler.snapshot(2)
            self.assertFalse(value['cpu']['available'])
            self.assertTrue(value['network']['available'])
