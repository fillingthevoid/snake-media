import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('alert_policy',Path(__file__).resolve().parents[1]/'tools/alert_policy.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)


class AlertPolicyTests(unittest.TestCase):
    def test_confirm_then_remind_and_recover_without_repeated_messages(self):
        state={};facts={'service:n8n':False};recipients={'service:n8n':['2']}
        events=policy.observe(state,facts,recipients,1000)
        self.assertEqual(events,[])
        events=policy.observe(state,facts,recipients,1300)
        self.assertEqual([(e['recipient'],e['kind'],e['key']) for e in events],[('2','problem','service:n8n')])
        policy.delivered(state,events[0],1300)
        self.assertEqual(policy.observe(state,facts,recipients,1600),[])
        events=policy.observe(state,facts,recipients,15700)
        self.assertEqual(events[0]['kind'],'reminder');policy.delivered(state,events[0],15700)
        self.assertEqual(policy.observe(state,{'service:n8n':True},recipients,16000),[])
        events=policy.observe(state,{'service:n8n':True},recipients,16300)
        self.assertEqual(events[0]['kind'],'recovery');policy.delivered(state,events[0],16300)
        self.assertEqual(policy.observe(state,{'service:n8n':True},recipients,16600),[])

    def test_failed_delivery_keeps_event_identity_and_does_not_cause_false_recovery(self):
        state={};recipients={'request:12':['2']};facts={'request:12':False}
        policy.observe(state,facts,recipients,1000)
        event=policy.observe(state,facts,recipients,1300)[0]
        retry=policy.observe(state,facts,recipients,1600)[0]
        self.assertEqual(event['id'],retry['id'])
        self.assertEqual(policy.observe(state,{'request:12':True},recipients,1900),[])
        self.assertEqual(policy.observe(state,{'request:12':True},recipients,2200),[])

    def test_unknown_does_not_recover_and_removed_recipient_is_not_notified(self):
        state={};recipients={'mounts':['2']}
        policy.observe(state,{'mounts':False},recipients,1000)
        event=policy.observe(state,{'mounts':False},recipients,1300)[0];policy.delivered(state,event,1300)
        self.assertEqual(policy.observe(state,{'mounts':None},recipients,1600),[])
        self.assertEqual(policy.observe(state,{'mounts':None},recipients,1900),[])
        self.assertEqual(policy.observe(state,{'mounts':True},{'mounts':[]},2200),[])

    def test_state_survives_restart_and_independent_requesters_never_mix(self):
        import json
        state={};r={'request:12':['2'],'request:13':['9']};f={'request:12':False,'request:13':False}
        policy.observe(state,f,r,1000)
        state=json.loads(json.dumps(state));events=policy.observe(state,f,r,1300)
        self.assertEqual(sorted((e['key'],e['recipient']) for e in events),[('request:12','2'),('request:13','9')])
        policy.delivered(state,events[0],1300)
        state=json.loads(json.dumps(state));remaining=policy.observe(state,f,r,1600)
        self.assertEqual(len(remaining),1);self.assertNotEqual(remaining[0]['recipient'],events[0]['recipient'])
