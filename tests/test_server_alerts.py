import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('server_alerts',ROOT/'tools/server_alerts.py')
alerts=importlib.util.module_from_spec(spec);spec.loader.exec_module(alerts)


class AlertRunnerTests(unittest.TestCase):
    def test_all_alerts_follow_owner_routing(self):
        state={};ops={'available':True,'lock':False,'requests':{'12':{'userId':'9','title':'Example','healthy':False}}}
        facts,recipients,titles=alerts.observations(None,ops,False,'2',{'2','9'},state,1000)
        self.assertEqual(recipients['request:12'],['2'])
        self.assertEqual(recipients['backup'],['2']);self.assertEqual(recipients['lock'],['2'])
        self.assertNotIn('Example',alerts.render([{'key':'backup','kind':'problem'}],titles))
        self.assertIn('Example',alerts.render([{'key':'request:12','kind':'problem'}],titles))

    def test_missing_metadata_does_not_forget_previously_delivered_request_alert(self):
        state={'request:12:9':{'key':'request:12','recipient':'9'}}
        facts,recipients,_=alerts.observations(None,{'available':False,'lock':None,'requests':{}},None,'2',{'2','9'},state,1000)
        self.assertIsNone(facts['request:12']);self.assertEqual(recipients['request:12'],['2'])

    def test_atomic_state_round_trip_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'state.json';alerts.save_state(p,{'schema':1,'issues':{'x':{'active':True}}})
            self.assertEqual(alerts.load_state(p)['issues']['x']['active'],True)
            self.assertFalse(Path(str(p)+'.tmp').exists())
            p.write_text('{bad')
            with self.assertRaises(ValueError):alerts.load_state(p)

    def test_private_channel_and_message_response_are_verified_before_ack(self):
        calls=[]
        def post(path,body):
            calls.append((path,body))
            if path=='/users/@me/channels':return {'id':'44','type':1,'recipients':[{'id':'2'}]}
            return {'id':'55','channel_id':'44','nonce':'event-test'}
        sender=alerts.DiscordSender('dummy');sender.post=post
        self.assertEqual(sender.send('2','Alert','event-test'),'55')
        self.assertEqual(calls[0],('/users/@me/channels',{'recipient_id':'2'}))
        self.assertEqual(calls[1][1]['allowed_mentions'],{'parse':[]})
        self.assertTrue(calls[1][1]['enforce_nonce'])
        sender.post=lambda *args:{'id':'44','type':1,'recipients':[{'id':'9'}]}
        with self.assertRaises(ValueError):sender.send('2','Alert','other-event')

    def test_failed_send_is_not_acknowledged_and_retry_keeps_nonce(self):
        state={'schema':1,'issues':{}};facts={'backup':False};recipients={'backup':['2']}
        alerts.policy.observe(state['issues'],facts,recipients,1000)
        events=alerts.policy.observe(state['issues'],facts,recipients,1300)
        class Sender:
            def send(self,*args):raise OSError('private technical detail')
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'state.json'
            sent,deferred=alerts.deliver_events(Sender(),p,state,events,{},1300)
            self.assertEqual((sent,deferred),(0,1));self.assertFalse(state['issues']['backup:2']['active'])
            retry=alerts.policy.observe(alerts.load_state(p)['issues'],facts,recipients,1600)
            self.assertEqual(retry[0]['id'],events[0]['id'])
