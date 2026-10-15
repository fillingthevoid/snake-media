"""Deliver n8n's leased catalog posts. All inventory decisions stay in n8n."""
import asyncio
import logging
import re
import time
import discord
from .media_reviews import marker,review_embed,review_post_view,rename_review_thread

log=logging.getLogger('snake_media')


class ReviewCatalogWorker:
    def __init__(self,client):
        self.client=client
        self.next_publish_at=0

    async def tick(self,body):
        backend=self.client.service.backend
        result=await backend.catalog(body|{'action':'poll'})
        if result.get('ok') is not True:
            raise ValueError('catalog_poll_failed')
        jobs=result.get('jobs',[])
        if not isinstance(jobs,list) or len(jobs)>10:raise ValueError('catalog_jobs_invalid')
        for job in jobs:
            if (not isinstance(job,dict) or not re.fullmatch(r'(movie|tv):[1-9][0-9]{0,19}',str(job.get('mediaKey','')))
                    or not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}',str(job.get('leaseId','')))):
                raise ValueError('catalog_job_invalid')
            delay=self.next_publish_at-time.monotonic()
            if delay>0:await asyncio.sleep(delay)
            self.next_publish_at=time.monotonic()+6
            error=None
            try:
                controller=self.client.reviews
                key=body['guildId']+':'+job['mediaKey']
                lock=controller.locks.setdefault(key,asyncio.Lock())
                async with lock:
                    data=await controller.call(body,op='summary',mediaKey=job['mediaKey'])
                    if data.get('mediaKey')!=job['mediaKey']:raise ValueError('catalog_identity_changed')
                    data,thread,starter=await controller.ensure_post(body,data)
                    await starter.edit(embed=review_embed(data,marker('post',body['guildId'],data['channelId'],data['mediaKey'])),
                        view=review_post_view(),allowed_mentions=discord.AllowedMentions.none())
                    await rename_review_thread(thread,data)
            except Exception as exc:
                error='missing_post' if isinstance(exc,discord.NotFound) and exc.code in (10003,10008) else 'publication_failed'
                log.warning('Review catalog publication deferred error_type=%s',type(exc).__name__)
            ack=await backend.catalog(body|{'action':'ack','mediaKey':job['mediaKey'],'leaseId':job['leaseId'],'ok':error is None,'error':error})
            if ack.get('ok') is not True:log.warning('Review catalog acknowledgement deferred')
        return len(jobs)

    async def run(self):
        await self.client.wait_until_ready()
        config=self.client.service.config
        owner=sorted(config.admin_user_ids,key=int)[0]
        while not self.client.is_closed():
            try:
                for channel_id in sorted(config.allowed_channel_ids,key=int):
                    channel=self.client.get_channel(int(channel_id)) or await self.client.fetch_channel(int(channel_id))
                    if not getattr(channel,'guild',None):continue
                    await self.tick({'userId':owner,'channelId':channel_id,'guildId':str(channel.guild.id)})
                    break
            except Exception as exc:
                log.warning('Review catalog sync deferred error_type=%s',type(exc).__name__)
            await asyncio.sleep(60)
