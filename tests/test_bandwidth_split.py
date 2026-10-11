import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))


class BandwidthTests(unittest.TestCase):
    def test_split_rates_average_generation_reset_and_stale_file(self):
        from bandwidth_metrics import SplitSampler
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'counters.json'
            sampler = SplitSampler(path)
            def tick(t, lan, internet, generation='a'):
                path.write_text(json.dumps(dict(version=1, generation=generation,
                    sampledAt=t, counters=dict(lan=lan, internet=internet, other=0))))
                return sampler.read(t)
            self.assertFalse(tick(100, 0, 0)['available'])
            r = tick(102, 2000000, 500000)
            self.assertEqual(r['lanMbps'], 8)
            self.assertEqual(r['internetMbps'], 2)
            self.assertIsNone(r['lanAverageMbps'])
            for t in range(104, 162, 2):
                r = tick(t, (t-100)*1000000, (t-100)*250000)
            self.assertEqual(r['lanAverageMbps'], 8)
            self.assertEqual(r['internetAverageMbps'], 2)
            self.assertFalse(sampler.read(170)['available'])
            self.assertFalse(tick(172, 1, 1)['available'])
            self.assertEqual(tick(174, 1, 1)['internetMbps'], 0)
            self.assertFalse(tick(176, 200, 200, 'b')['available'])
            path.write_text('{broken')
            self.assertFalse(sampler.read(178)['available'])

    def test_duplicate_samples_do_not_divide_by_zero_or_fake_idle(self):
        from bandwidth_metrics import SplitSampler
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'c.json'; s=SplitSampler(p)
            for t, count in [(100,0),(102,1000000)]:
                p.write_text(json.dumps(dict(version=1,generation='a',sampledAt=t,
                    counters=dict(lan=count,internet=0,other=0))))
                s.read(t)
            self.assertEqual(s.read(104)['lanMbps'],4)
            self.assertFalse(s.read(110)['available'])

    def test_nft_parser_rejects_missing_duplicate_negative_and_wrong_table(self):
        from network_accounting import parse_counters
        def item(name, count):return {'counter':dict(family='netdev',table='snake_upload_metrics',name=name,bytes=count,packets=0)}
        data={'nftables':[item('lan',10),item('internet',20),item('other',0)]}
        self.assertEqual(parse_counters(data),dict(lan=10,internet=20,other=0))
        for bad in [data['nftables'][:2],data['nftables']+[item('lan',10)],
                    [item('lan',-1),item('internet',20),item('other',0)]]:
            with self.assertRaises(ValueError):parse_counters({'nftables':bad})

    def test_generated_rules_classify_destinations_and_reject_injection(self):
        from network_accounting import rules, classify
        topology={'eno2':['192.168.0.0/24','fe80::/64']}
        for address, expected in [('192.168.0.47','lan'),('8.8.8.8','internet'),
            ('100.98.184.36','other'),('10.0.0.1','other'),('224.0.0.251','lan'),
            ('fe80::1','lan'),('2001:4860:4860::8888','internet'),('fd00::1','other')]:
            self.assertEqual(classify(address,topology['eno2']),expected)
        text=rules(topology)
        self.assertIn('hook egress device "eno2"',text)
        self.assertIn('counter name lan return',text)
        self.assertNotIn('drop',text)
        self.assertNotIn('flush ruleset',text)
        with self.assertRaises(ValueError):rules({'eno2"; drop;':[]})

    def test_performance_sampler_keeps_physical_total_when_split_is_missing(self):
        from performance_metrics import PerformanceSampler
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); interface=root/'net/eth0'
            (interface/'statistics').mkdir(parents=True);(interface/'device').mkdir()
            (interface/'operstate').write_text('up');(interface/'statistics/tx_bytes').write_text('0')
            stat=root/'stat';stat.write_text('cpu 0 0 0 0 0 0 0 0')
            s=PerformanceSampler(stat,root/'net',split_file=root/'missing')
            s.tick(100);s.tick(102)
            r=s.snapshot(102)['network']
            self.assertEqual(r['uploadMbps'],0)
            self.assertFalse(r['split']['available'])
