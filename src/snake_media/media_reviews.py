"""Discord review presentation and durable delivery receipts. n8n owns every vote."""
import asyncio
import hashlib
import json
import logging
import sqlite3
import weakref
import discord
from .n8n_client import MediaReply

log=logging.getLogger('snake_media')
ERRORS={'denied':"⛔ This Discord account isn't authorized to review here.",
    'unconfigured':'Reviews aren’t set up yet. The owner can use /setupreview.',
    'invalid_notice':'This review button expired. You can still react to the title’s review post.',
    'missing_identity':'This title doesn’t have review details yet.',
    'unknown_post':'This isn’t a registered Snake Media review post.'}

class ReviewJournal:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS review_deliveries (key TEXT PRIMARY KEY, receipt TEXT NOT NULL)');self.db.commit()
    def __enter__(self):return self
    def __exit__(self,*args):self.db.close()
    def get(self,key):
        row=self.db.execute('SELECT receipt FROM review_deliveries WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None
    def begin(self,key):
        with self.db:self.db.execute("INSERT OR IGNORE INTO review_deliveries VALUES (?, '{}')",(key,))
    def save(self,key,value):
        old=self.get(key)
        if old and old!=value:raise ValueError('review_receipt_conflict')
        with self.db:self.db.execute('INSERT INTO review_deliveries VALUES (?,?) ON CONFLICT(key) DO UPDATE SET receipt=excluded.receipt',(key,json.dumps(value)))

def destination_error(channel,guild_id):
    if (not isinstance(channel,(discord.ForumChannel,discord.TextChannel))
            or getattr(channel,'type',None)==discord.ChannelType.media):
        return 'Choose a forum or text channel.'
    if channel.guild.id!=int(guild_id):return 'Choose a channel in the same server.'
    p=channel.permissions_for(channel.guild.me)
    required={'view_channel':'View Channel','send_messages':'Send Messages / Create Posts',
        'read_message_history':'Read Message History','embed_links':'Embed Links',
        'add_reactions':'Add Reactions','send_messages_in_threads':'Send Messages in Threads'}
    if isinstance(channel,discord.TextChannel):required['create_public_threads']='Create Public Threads'
    missing=[label for name,label in required.items() if not getattr(p,name,False)]
    if missing:return 'Please give Snake Media these permissions: '+', '.join(missing)+'.'
    if isinstance(channel,discord.ForumChannel) and channel.flags.require_tag and not any(not t.moderated for t in channel.available_tags):
        return 'This forum requires a tag. Add a tag the bot can use first.'
    return None

def marker(kind,*parts):return 'snake-review-'+kind+':'+hashlib.sha256(':'.join(parts).encode()).hexdigest()[:24]

def review_embed(data,footer):
    title=discord.utils.escape_mentions(str(data['title']))[:250]
    embed=discord.Embed(title=title,description=str(data.get('summary',''))+'\n\nReact ❤️ Loved it or 🙃 Not for me. Your latest choice counts.',colour=0x2ECC71)
    poster=MediaReply('',poster_url=data.get('posterUrl')).poster_url
    if poster:embed.set_thumbnail(url=poster)
    embed.set_footer(text=footer);return embed

class ReviewController:
    def __init__(self,client,journal):
        self.client=client;self.service=client.service;self.journal=journal
        self.locks=weakref.WeakValueDictionary()
    async def call(self,body,**changes):
        data=await self.service.backend.review(body|changes)
        if not data.get('ok'):raise ValueError(data.get('error','review_failed'))
        return data
    async def vote(self,body,vote):
        if body['userId'] not in self.service.allowed_users:return ERRORS['denied']
        try:
            data=await self.call(body,op='resolve' if body.get('noticeId') else 'lookup')
            key=body['guildId']+':'+data['mediaKey']
            lock=self.locks.setdefault(key,asyncio.Lock())
            async with lock:
                data=await self.call(body,op='vote',vote=vote)
                try:await self.publish(body,data)
                except Exception as exc:
                    log.warning('Review publication deferred error_type=%s',type(exc).__name__)
                    return '✅ Your review is saved. I couldn’t update the review post yet. Tap again to retry.'
            return '✅ Review saved: '+('❤️ Loved it.' if vote=='loved' else '🙃 Not for me.')
        except ValueError as exc:
            return ERRORS.get(str(exc),'⚠️ Your review couldn’t be saved right now. Please try again.')
        except Exception as exc:
            log.warning('Review request failed error_type=%s',type(exc).__name__)
            return '⚠️ Your review couldn’t be saved right now. Please try again.'

    async def find_message(self,channel,tag,limit=100):
        async for message in channel.history(limit=limit):
            if message.author.id==self.client.user.id and any(e.footer.text==tag for e in message.embeds):return message
        return None

    async def publish(self,body,data):
        destination=self.client.get_channel(int(data['channelId'])) or await self.client.fetch_channel(int(data['channelId']))
        error=destination_error(destination,body['guildId'])
        if error:raise ValueError('review_permissions_missing')
        tag=marker('post',body['guildId'],data['channelId'],data['mediaKey'])
        post=data.get('post') or self.journal.get(tag)
        if post is None or not post:
            # Search before creation, including after an acceptance/save interruption.
            found=None
            if isinstance(destination,discord.ForumChannel):
                threads=list(destination.threads)
                async for t in destination.archived_threads(limit=100):threads.append(t)
                for thread in threads:
                    if thread.name!=data['title'][:100]:continue
                    candidate=await thread.fetch_message(thread.id)
                    if candidate.author.id==self.client.user.id and any(e.footer.text==tag for e in candidate.embeds):found=candidate;break
            else:found=await self.find_message(destination,tag,100)
            if found:
                if isinstance(destination,discord.ForumChannel):thread=found.channel
                else:thread=found.thread or await found.create_thread(name=data['title'][:100])
                post={'threadId':str(thread.id),'messageId':str(found.id),'messageChannelId':str(found.channel.id)}
            elif post=={}:
                raise ValueError('review_creation_outcome_unknown')
            else:
                self.journal.begin(tag)
                if isinstance(destination,discord.ForumChannel):
                    tags=[t for t in destination.available_tags if not t.moderated][:1] if destination.flags.require_tag else []
                    result=await destination.create_thread(name=data['title'][:100],embed=review_embed(data,tag),applied_tags=tags,allowed_mentions=discord.AllowedMentions.none())
                    thread,starter=result.thread,result.message
                else:
                    starter=await destination.send(embed=review_embed(data,tag),allowed_mentions=discord.AllowedMentions.none())
                    thread=await starter.create_thread(name=data['title'][:100])
                post={'threadId':str(thread.id),'messageId':str(starter.id),'messageChannelId':str(starter.channel.id)}
            self.journal.save(tag,post)
        data=await self.call(body,op='bind',mediaKey=data['mediaKey'],**post)
        thread=self.client.get_channel(int(post['threadId'])) or await self.client.fetch_channel(int(post['threadId']))
        if thread.archived:await thread.edit(archived=False)
        channel=self.client.get_channel(int(post['messageChannelId'])) or await self.client.fetch_channel(int(post['messageChannelId']))
        starter=await channel.fetch_message(int(post['messageId']))
        if starter.author.id!=self.client.user.id:raise ValueError('review_starter_author_changed')
        comment_tag=marker('comment',body['guildId'],data['channelId'],data['mediaKey'],body['userId'])
        receipt=self.journal.get(comment_tag);comment=None
        if data.get('commentId') or receipt:
            comment=await thread.fetch_message(int(data.get('commentId') or receipt['messageId']))
        else:comment=await self.find_message(thread,comment_tag)
        comment_embed=discord.Embed(description=f"<@{body['userId']}> — "+('❤️ Loved it' if data['vote']=='loved' else '🙃 Not for me'),colour=0x2ECC71)
        comment_embed.set_footer(text=comment_tag)
        if comment:
            if comment.author.id!=self.client.user.id:raise ValueError('review_comment_author_changed')
            await comment.edit(embed=comment_embed,allowed_mentions=discord.AllowedMentions.none())
        else:
            if receipt=={}:raise ValueError('review_comment_outcome_unknown')
            self.journal.begin(comment_tag)
            comment=await thread.send(embed=comment_embed,allowed_mentions=discord.AllowedMentions.none())
        self.journal.save(comment_tag,{'messageId':str(comment.id)})
        await self.call(body,op='comment',mediaKey=data['mediaKey'],commentId=str(comment.id))
        data=await self.call(body,op='summary',mediaKey=data['mediaKey'])
        await starter.edit(embed=review_embed(data,tag),allowed_mentions=discord.AllowedMentions.none())
        for emoji in ('❤️','🙃'):await starter.add_reaction(emoji)
