import unittest
from snake_media.notifications import NotificationDelivery

class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_send_cools_down_without_losing_its_retry(self):
        class Transport:
            async def poll(self,exclude=()):
                row={'notificationKey':'bad','destinationId':'333',
                     'payload':{'userId':'111','messageId':'444','text':'Ready'}}
                return [] if 'bad' in exclude else [row]
            async def acknowledge(self,*args): pass
        attempts=[]; now=[0]
        async def send(*args, **options): attempts.append(now[0]);raise OSError('offline')
        delivery=NotificationDelivery(Transport(),send,{'111'},{'333'},clock=lambda:now[0])
        with self.assertLogs('snake_media',level='WARNING'): await delivery.tick()
        now[0]=30;await delivery.tick()
        now[0]=60
        with self.assertLogs('snake_media',level='WARNING'): await delivery.tick()
        now[0]=120;await delivery.tick()
        now[0]=180
        with self.assertLogs('snake_media',level='WARNING'): await delivery.tick()
        self.assertEqual(attempts,[0,60,180])

    async def test_failed_first_send_does_not_block_later_notice(self):
        class Transport:
            async def poll(self,exclude=()):
                return [{'notificationKey':key,'destinationId':'333','payload':
                         {'userId':'111','messageId':message,'text':'Ready'}}
                        for key,message in [('bad','444'),('good','445')]]
            async def acknowledge(self,*args): pass
        sent=[]
        async def send(channel,message,text, **options):
            if message=='444': raise OSError('unavailable')
            sent.append(message);return '555'
        delivery=NotificationDelivery(Transport(),send,{'111'},{'333'})
        with self.assertLogs('snake_media',level='WARNING'): await delivery.tick()
        self.assertEqual(sent,['445'])

    async def test_failed_old_ack_does_not_block_new_delivery(self):
        class Transport:
            async def poll(self,exclude=()):
                return [{'notificationKey':'new','destinationId':'333',
                         'payload':{'userId':'111','messageId':'445','text':'Ready'}}]
            async def acknowledge(self,key,message):
                if key=='old': raise OSError('unavailable')
        sent=[]
        async def send(channel,message,text, **options): sent.append(message);return '555'
        delivery=NotificationDelivery(Transport(),send,{'111'},{'333'})
        delivery.pending_acks['old']='554'
        with self.assertLogs('snake_media',level='WARNING'): await delivery.tick()
        self.assertEqual(sent,['445'])
        self.assertEqual(delivery.pending_acks,{'old':'554'})

    async def test_successful_send_is_not_repeated_when_ack_fails(self):
        class Transport:
            calls=0
            async def poll(self,exclude=()): return [{'notificationKey':'k','destinationId':'333','payload':{'userId':'111','messageId':'444','text':'Ready'}}]
            async def acknowledge(self,key,message_id):
                self.calls+=1
                if self.calls==1: raise OSError('network')
        sent=[]
        async def send(channel,message,text, **options):sent.append((channel,message,text));return '555'
        d=NotificationDelivery(Transport(),send,{'111'},{'333'})
        with self.assertLogs('snake_media',level='WARNING'): await d.tick()
        await d.tick()
        self.assertEqual(sent,[('333','444','Ready')])

    async def test_removed_users_and_unapproved_channels_never_receive_messages(self):
        class Transport:
            async def poll(self,exclude=()):return [{'notificationKey':'k','destinationId':'666','payload':{'userId':'111','messageId':'444','text':'Ready'}},{'notificationKey':'l','destinationId':'333','payload':{'userId':'222','messageId':'444','text':'Ready'}}]
            async def acknowledge(self,*args):pass
        sent=[]
        async def send(*args, **options):sent.append(args)
        await NotificationDelivery(Transport(),send,{'111'},{'333'}).tick()
        self.assertEqual(sent,[])

class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_authenticated_poll_and_ack_contract(self):
        from aiohttp import web
        from aiohttp.test_utils import TestServer
        from snake_media.notifications import NotificationTransport
        seen=[]
        async def handler(request):
            seen.append((request.headers.get('X-Snake-Media-Key'),await request.json()))
            return web.json_response({'version':1,'notifications':[],'acknowledged':True})
        app=web.Application();app.router.add_post('/queue',handler)
        server=TestServer(app);await server.start_server()
        try:
            async with NotificationTransport(str(server.make_url('/queue')),'dummy') as client:
                self.assertEqual(await client.poll(),[])
                await client.acknowledge('discord:333:444:movie:12','555')
            self.assertEqual(seen,[('dummy',{'action':'poll'}),('dummy',{'action':'ack','notificationKey':'discord:333:444:movie:12','messageId':'555'})])
        finally:await server.close()
