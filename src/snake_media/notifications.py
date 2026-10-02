"""Outbound notification transport and Discord delivery; n8n decides availability."""
import asyncio
import json
import logging
from collections import deque
import aiohttp

log = logging.getLogger('snake_media')

class NotificationTransport:
    def __init__(self, url, secret):
        self.url, self.secret, self.session = url, secret, None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20, connect=5),
            headers={'X-Snake-Media-Key':self.secret},trust_env=False,cookie_jar=aiohttp.DummyCookieJar())
        return self

    async def __aexit__(self,*args):
        await self.session.close()

    async def _post(self, body):
        async with self.session.post(self.url,json=body,allow_redirects=False) as response:
            if response.status != 200 or response.content_type != 'application/json':
                raise ValueError('notification_http_error')
            raw=bytearray()
            async for chunk in response.content.iter_chunked(8192):
                raw.extend(chunk)
                if len(raw)>65536: raise ValueError('notification_response_too_large')
            data=json.loads(raw)
            if not isinstance(data,dict) or data.get('version')!=1: raise ValueError('notification_contract_error')
            return data

    async def poll(self):
        data=await self._post({'action':'poll'})
        rows=data.get('notifications')
        if not isinstance(rows,list) or len(rows)>10: raise ValueError('notification_batch_error')
        return rows

    async def acknowledge(self,key,message_id):
        data=await self._post({'action':'ack','notificationKey':key,'messageId':message_id})
        if data.get('acknowledged') is not True: raise ValueError('notification_ack_error')

class NotificationDelivery:
    def __init__(self,transport,send,users,channels,journal=None):
        self.transport,self.send,self.users,self.channels=transport,send,users,channels
        self.journal=journal
        self.pending_acks=journal.pending() if journal is not None else {}
        self.delivered=deque(maxlen=1000)

    async def _acknowledge(self,key,message_id):
        if self.journal is not None:
            self.journal.record(key,message_id)
        await self.transport.acknowledge(key,message_id)
        if self.journal is not None:
            self.journal.acknowledge(key)
        del self.pending_acks[key]

    async def tick(self):
        try:
            for key,message_id in list(self.pending_acks.items()):
                await self._acknowledge(key,message_id)
            for row in await self.transport.poll():
                if not isinstance(row,dict): continue
                key=row.get('notificationKey'); channel=row.get('destinationId'); payload=row.get('payload')
                if not isinstance(key,str) or not 1<=len(key)<=300 or not isinstance(payload,dict): continue
                if key in self.delivered or (self.journal is not None and self.journal.get(key)): continue
                if payload.get('userId') not in self.users or channel not in self.channels: continue
                message=payload.get('messageId'); text=payload.get('text')
                if not isinstance(message,str) or not message.isascii() or not message.isdigit(): continue
                if not isinstance(text,str) or not 1<=len(text)<=1800: continue
                notice_id=str(row.get('id',''))
                options={}
                if (payload.get('retentionControls') is not False and notice_id.isascii()
                        and notice_id.isdigit() and 0<int(notice_id)<10**16):
                    options['notice_id']=notice_id
                for field, option in [('posterUrl', 'poster_url'), ('jellyfinUrl', 'jellyfin_url'), ('localJellyfinUrl', 'local_jellyfin_url')]:
                    if isinstance(payload.get(field), str):
                        options[option] = payload[field]
                sent=await self.send(channel,message,text,**options)
                self.delivered.append(key)
                self.pending_acks[key]=str(sent)
                await self._acknowledge(key,str(sent))
        except Exception as exc:
            log.warning('Notification delivery deferred error_type=%s',type(exc).__name__)

    async def run(self,client):
        while not client.is_closed():
            await client.wait_until_ready()
            await self.tick()
            await asyncio.sleep(60)
