"""Outbound notification transport and Discord delivery; n8n decides availability."""
import asyncio
import json
import logging
import time
from collections import deque, OrderedDict
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

    async def poll(self,exclude=()):
        body={'action':'poll'}
        if exclude: body['excludeNotificationKeys']=list(exclude)[:1000]
        data=await self._post(body)
        rows=data.get('notifications')
        if not isinstance(rows,list) or len(rows)>10: raise ValueError('notification_batch_error')
        return rows

    async def acknowledge(self,key,message_id):
        data=await self._post({'action':'ack','notificationKey':key,'messageId':message_id})
        if data.get('acknowledged') is not True: raise ValueError('notification_ack_error')

class NotificationDelivery:
    def __init__(self,transport,send,users,channels,journal=None,clock=time.monotonic,wall_clock=time.time):
        self.transport,self.send,self.users,self.channels=transport,send,users,channels
        self.journal=journal
        self.pending_acks=journal.pending() if journal is not None else {}
        self.delivered=deque(maxlen=1000)
        self.clock,self.wall_clock=clock,wall_clock
        self.retries=OrderedDict()
        if journal is not None:
            wall_now, runtime_now = wall_clock(), clock()
            for key, (attempts, due) in journal.retries().items():
                # Saved wall time survives process restarts. Cap clock corrections
                # at the existing maximum delay, then use monotonic time at runtime.
                self.retries[key] = (attempts, runtime_now + max(0, min(900, due - wall_now)))

    def _defer(self,key):
        attempts=self.retries.get(key,(0,0))[0]+1
        delay=min(900,60*2**min(attempts-1,4))
        self.retries[key]=(min(attempts,5),self.clock()+delay)
        self.retries.move_to_end(key)
        while len(self.retries)>1000: self.retries.popitem(last=False)
        if self.journal is not None:
            try:
                now=self.wall_clock()
                self.journal.defer(key,min(attempts,5),now+delay,now)
            except Exception as exc:
                # Keep the in-memory delay and other recipients moving when
                # private state is temporarily unwritable.
                log.warning('Notification retry storage deferred error_type=%s',type(exc).__name__)

    async def _acknowledge(self,key,message_id):
        if self.journal is not None:
            self.journal.record(key,message_id)
        await self.transport.acknowledge(key,message_id)
        if self.journal is not None:
            self.journal.acknowledge(key)
        del self.pending_acks[key]

    async def tick(self):
        for key,message_id in list(self.pending_acks.items()):
            try:
                await self._acknowledge(key,message_id)
            except Exception as exc:
                log.warning('Notification acknowledgement deferred error_type=%s',type(exc).__name__)
        try:
            excluded=list(self.pending_acks)+[key for key,(_,due) in self.retries.items() if due>self.clock()]
            rows=await self.transport.poll(exclude=excluded[:1000])
        except Exception as exc:
            log.warning('Notification polling deferred error_type=%s',type(exc).__name__)
            return
        for row in rows:
            key=None
            try:
                if not isinstance(row,dict): continue
                key=row.get('notificationKey'); channel=row.get('destinationId'); payload=row.get('payload')
                if not isinstance(key,str) or not 1<=len(key)<=300 or not isinstance(payload,dict): continue
                if self.retries.get(key,(0,0))[1]>self.clock(): continue
                if key in self.delivered or (self.journal is not None and self.journal.get(key)): continue
                if payload.get('userId') not in self.users or channel not in self.channels:
                    self._defer(key)
                    continue
                message=payload.get('messageId'); text=payload.get('text')
                if (not isinstance(message,str) or not message.isascii() or not message.isdigit()
                        or not isinstance(text,str) or not 1<=len(text)<=1800):
                    self._defer(key)
                    continue
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
                self.retries.pop(key,None)
                await self._acknowledge(key,str(sent))
            except Exception as exc:
                if key is not None and key not in self.pending_acks: self._defer(key)
                log.warning('Notification delivery deferred error_type=%s',type(exc).__name__)

    async def run(self,client):
        while not client.is_closed():
            await client.wait_until_ready()
            await self.tick()
            await asyncio.sleep(60)
