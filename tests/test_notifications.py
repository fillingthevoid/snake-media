import unittest
from snake_media.notifications import NotificationDelivery

class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_send_is_not_repeated_when_ack_fails(self):
        class Transport:
            calls=0
            async def poll(self): return [{'notificationKey':'k','destinationId':'333','payload':{'userId':'111','messageId':'444','text':'Ready'}}]
            async def acknowledge(self,key,message_id):
                self.calls+=1
                if self.calls==1: raise OSError('network')
        sent=[]
        async def send(channel,message,text):sent.append((channel,message,text));return '555'
        d=NotificationDelivery(Transport(),send,{'111'},{'333'})
        with self.assertLogs('snake_media',level='WARNING'): await d.tick()
        await d.tick()
        self.assertEqual(sent,[('333','444','Ready')])

    async def test_removed_users_and_unapproved_channels_never_receive_messages(self):
        class Transport:
            async def poll(self):return [{'notificationKey':'k','destinationId':'666','payload':{'userId':'111','messageId':'444','text':'Ready'}},{'notificationKey':'l','destinationId':'333','payload':{'userId':'222','messageId':'444','text':'Ready'}}]
            async def acknowledge(self,*args):pass
        sent=[]
        async def send(*args):sent.append(args)
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
