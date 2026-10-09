import logging
import asyncio
import time
import json
import aiohttp

import discord
from discord import app_commands

from .requests import IncomingMessage
from .service import RequestService
from .notifications import NotificationDelivery
from .confirmations import CUSTOM_ID, presentation, edit_presentation, notification_view
from .n8n_client import MediaReply
from .command_menu import menu_text, menu_choices, NAVIGATION
from .request_prompt import RequestTitleModal

log = logging.getLogger("snake_media")


class SnakeMediaClient(discord.Client):
    def __init__(self, service: RequestService, notification_transport=None, notification_journal=None, card_registry=None):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(intents=intents, max_messages=None,
                         allowed_mentions=discord.AllowedMentions.none())
        self.service = service
        self.notification_task = None
        self.notification_worker = None
        self.notification_transport = notification_transport
        self.notification_journal = notification_journal
        self.card_registry = card_registry
        self.card_cleanup_task = None
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(app_commands.Command(name='authorize',
            description='Owner only: authorize a Discord account in Snake Media.',
            callback=self.authorize_command))
        self.tree.add_command(app_commands.Command(name='status',
            description='Show your media requests, download progress and expiry.',
            callback=self.status_command))
        self.tree.add_command(app_commands.Command(name='serverstatus',
            description='Check server storage, media services and Jellyfin streaming.',
            callback=self.server_status_command))
        self.tree.add_command(app_commands.Command(name='request',
            description='Request a movie or series; review the poster before confirming.',
            callback=self.request_command))
        self.tree.add_command(app_commands.Command(name='recommend',
            description='Find movies or shows based on your requests and a chosen genre.',
            callback=self.recommend_command))
        self.tree.add_command(app_commands.Command(name='help',
            description='Show request, season, expiry and status instructions.',
            callback=self.help_command))
        self.tree.add_command(app_commands.Command(name='extend',
            description='Choose one of your requests and extend its expiry.',
            callback=self.extend_command))
        self.tree.add_command(app_commands.Command(name='keep',
            description='Choose one of your requests to keep permanently.',
            callback=self.keep_command))

    async def help_command(self, interaction: discord.Interaction):
        await self.menu_command(interaction, 'help')

    async def menu_command(self, interaction, section):
        if section == 'request':
            await self.request_command(interaction)
            return
        if section in ('recommend', 'status', 'serverstatus', 'extend', 'keep'):
            await self.read_command(interaction, section)
            return
        await interaction.response.defer(ephemeral=True, thinking=getattr(interaction, 'type', None) != discord.InteractionType.component)
        if not self.service.command_allowed(str(interaction.user.id), str(interaction.channel_id), interaction.guild_id):
            text = "⛔ This Discord account isn't authorized to use Snake Media here."
            view = None
        else:
            text = menu_text(section)
            view = discord.ui.View(timeout=None)
            for choice in menu_choices(section):
                view.add_item(discord.ui.Button(label=choice['label'],
                    custom_id='snake_menu:'+choice['action'], style=discord.ButtonStyle.secondary))
        sent = await interaction.followup.send(text, ephemeral=True, view=view, wait=True,
                                        allowed_mentions=discord.AllowedMentions.none())
        self.track_controls(sent, str(interaction.user.id), str(interaction.channel_id), view, interaction)

    async def request_command(self, interaction: discord.Interaction, title: str = ''):
        if not title:
            if not self.service.command_allowed(str(interaction.user.id), str(interaction.channel_id), interaction.guild_id):
                await interaction.response.send_message("⛔ This Discord account isn't authorized to use Snake Media here.", ephemeral=True)
                return
            await interaction.response.send_modal(RequestTitleModal(self, str(interaction.user.id)))
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not self.service.command_allowed(str(interaction.user.id), str(interaction.channel_id), interaction.guild_id):
            await interaction.followup.send("⛔ This Discord account isn't authorized to use Snake Media here.", ephemeral=True)
            return
        if not title.strip() or len(title) > 1600:
            await interaction.followup.send('Enter a movie or series title.', ephemeral=True)
            return
        card = None
        try:
            card = await interaction.channel.send('🔎 Checking your request…', allowed_mentions=discord.AllowedMentions.none())
            incoming = IncomingMessage(text=f'<@{self.user.id}> add {title.strip()}',
                user_id=str(interaction.user.id), username=interaction.user.name,
                channel_id=str(interaction.channel_id), guild_id=str(interaction.guild_id),
                is_bot=False, message_id=str(card.id),
                requested_at=discord.utils.snowflake_time(card.id).isoformat(timespec='milliseconds').replace('+00:00', 'Z'))
            reply = await self.service.handle(incoming, str(self.user.id))
            self.wake_notifications()
            options = presentation(reply or '⚠️ This request could not be prepared.')
            options.setdefault('view', None)
            await card.edit(**options)
            self.remember_card(reply, card, str(interaction.user.id), str(interaction.channel_id))
            await interaction.followup.send('Your request: '+card.jump_url, ephemeral=True)
        except Exception as exc:
            log.error('Slash request failed error_type=%s', type(exc).__name__)
            await interaction.followup.send('⚠️ Request could not be confirmed. Check its card before trying again.', ephemeral=True)

    async def authorize_command(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        reply = await self.service.authorize_user(str(interaction.user.id),
            str(interaction.channel_id), str(interaction.guild_id) if interaction.guild_id else None,
            user_id.strip())
        await interaction.followup.send(reply, ephemeral=True,
                                       allowed_mentions=discord.AllowedMentions.none())

    async def status_command(self, interaction: discord.Interaction, title: str = ''):
        await self.read_command(interaction, f'status {title}')

    async def server_status_command(self, interaction: discord.Interaction):
        await self.read_command(interaction, 'serverstatus')

    async def recommend_command(self, interaction: discord.Interaction):
        await self.read_command(interaction, 'recommend')

    async def extend_command(self, interaction: discord.Interaction, title: str = '',
                             days: app_commands.Range[int, 1, 3650] = 7):
        await self.read_command(interaction, f'extend {title.strip()} {days} days' if title.strip() else 'extend')

    async def keep_command(self, interaction: discord.Interaction, title: str = ''):
        await self.read_command(interaction, f'keep {title.strip()} permanently' if title.strip() else 'keep')

    async def read_command(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer(ephemeral=True, thinking=getattr(interaction, 'type', None) != discord.InteractionType.component)
        incoming = IncomingMessage(text=f'<@{self.user.id}> {text}',
            user_id=str(interaction.user.id), username=interaction.user.name,
            channel_id=str(interaction.channel_id),
            guild_id=str(interaction.guild_id) if interaction.guild_id else None,
            is_bot=False, message_id=str(interaction.id),
            requested_at=discord.utils.snowflake_time(interaction.id).isoformat(timespec='milliseconds').replace('+00:00', 'Z'))
        reply = await self.service.handle(incoming, str(self.user.id))
        sent = await interaction.followup.send(ephemeral=True, wait=True,
            **presentation(reply or 'Use Snake Media in an authorized server channel.'))
        self.remember_card(reply, sent, str(interaction.user.id), str(interaction.channel_id), interaction)

    async def setup_hook(self):
        if self.card_registry is not None:
            self.card_cleanup_task = asyncio.create_task(self.run_card_cleanup())
        guilds = set()
        for channel_id in self.service.config.allowed_channel_ids:
            try:
                channel = await self.fetch_channel(int(channel_id))
                if getattr(channel, 'guild', None):
                    guilds.add(channel.guild.id)
            except discord.HTTPException as exc:
                log.warning('Slash command channel lookup failed error_type=%s', type(exc).__name__)
        for guild_id in guilds:
            try:
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                log.info('Slash commands synchronized guild_id=%s', guild_id)
            except discord.HTTPException as exc:
                log.warning('Slash command sync failed error_type=%s', type(exc).__name__)
        if self.notification_transport:
            worker = NotificationDelivery(self.notification_transport, self.send_notification,
                self.service.allowed_users, self.service.config.allowed_channel_ids,
                journal=self.notification_journal)
            self.notification_worker = worker
            self.notification_task = asyncio.create_task(worker.run(self))

    def wake_notifications(self):
        if self.notification_worker is not None:
            self.notification_worker.wake()

    async def send_notification(self, channel_id, message_id, text, notice_id=None,
                                poster_url=None, jellyfin_url=None, local_jellyfin_url=None, nonce=None, owner_id=None):
        channel = self.get_channel(int(channel_id)) or await self.fetch_channel(int(channel_id))
        reference = discord.MessageReference(message_id=int(message_id), channel_id=int(channel_id),
                                             fail_if_not_exists=False)
        reply = MediaReply(discord.utils.escape_mentions(discord.utils.escape_markdown(text)),
                           poster_url, jellyfin_url, notice_id, local_jellyfin_url)
        options = presentation(reply)
        options.setdefault('view', None)
        original = self.card_registry.request_card(channel_id, message_id, owner_id) if self.card_registry and owner_id else None
        if original:
            try:
                message = await asyncio.wait_for(channel.fetch_message(int(original)), timeout=10)
                if message.author.id != self.user.id:
                    raise ValueError('original_card_author_changed')
                if not options['embed'] and message.embeds:
                    embed = message.embeds[0].copy()
                    embed.description = str(reply)
                    options.update(content=None, embed=embed)
                await asyncio.wait_for(message.edit(**options), timeout=10)
                self.remember_card(reply, message, owner_id, channel_id)
                log.info('Request card updated channel_id=%s', channel_id)
                return str(message.id)
            except (discord.NotFound, discord.Forbidden):
                log.info('Original request card unavailable; using notification fallback')
            # Temporary/unknown edit outcomes propagate to the existing durable
            # retry worker. Repeating an edit is safe; a new post may duplicate it.
        # discord.py enforces supplied nonce uniqueness for Discord's recent window.
        message = await channel.send(reference=reference, nonce=nonce, **options)
        if owner_id:
            self.remember_card(reply, message, owner_id, channel_id)
        log.info('Completion notice delivered channel_id=%s', channel_id)
        return str(message.id)

    async def close(self):
        if self.card_cleanup_task:
            self.card_cleanup_task.cancel()
            await asyncio.gather(self.card_cleanup_task, return_exceptions=True)
        if self.notification_task:
            self.notification_task.cancel()
            await asyncio.gather(self.notification_task, return_exceptions=True)
        await super().close()

    def track_controls(self, message, owner, destination, view, interaction=None):
        if self.card_registry is None or message is None or view is None:
            return
        if not any(getattr(b, 'custom_id', None) for b in view.children):
            return
        links = [{'label': b.label, 'url': b.url} for b in view.children if getattr(b, 'url', None)]
        try:
            self.card_registry.track(destination, str(message.id), owner, links=links,
                webhook_id=str(interaction.application_id) if interaction else None,
                webhook_token=interaction.token if interaction else None)
        except Exception as exc:
            log.warning('Control deadline storage deferred error_type=%s', type(exc).__name__)

    def renew_controls(self, interaction):
        if self.card_registry is None or getattr(interaction, 'message', None) is None:
            return
        destination, message, owner = str(interaction.channel_id), str(interaction.message.id), str(interaction.user.id)
        old = self.card_registry.control(destination, message)
        private = bool(old and old.get('webhook_token'))
        self.card_registry.touch(destination, message, owner,
            webhook_id=str(interaction.application_id) if private else None,
            webhook_token=interaction.token if private else None)

    def remember_card(self, reply, message, owner, destination, interaction=None):
        if self.card_registry is None or message is None:
            return
        original = getattr(reply, 'request_message_id', None)
        if original:
            try:
                self.card_registry.remember_request(destination, original, str(message.id), owner)
            except Exception as exc:
                log.warning('Active card storage deferred error_type=%s', type(exc).__name__)
        group = ('pending:' + str(reply.pending_id) if getattr(reply, 'choices', None)
                 else 'notice:' + str(reply.notice_id) if getattr(reply, 'notice_id', None) else None)
        if group:
            try:
                self.card_registry.remember(group, destination, str(message.id), owner)
            except Exception as exc:
                log.warning('Card reference storage deferred error_type=%s', type(exc).__name__)
        self.track_controls(message, owner, destination, presentation(reply).get('view'), interaction)

    async def run_card_cleanup(self):
        while not self.is_closed():
            await self.wait_until_ready()
            try:
                await self.cleanup_cards()
            except Exception as exc:
                log.warning('Related card cleanup retry error_type=%s', type(exc).__name__)
            await asyncio.sleep(5)

    async def cleanup_cards(self):
        if self.card_registry is None:
            return
        self.card_registry.compact(time.time() - 90 * 86400)
        self.card_registry.expire(time.time())
        for row in self.card_registry.pending(time.time()):
            destination, ident = row['destination_id'], row['message_id']
            try:
                if row.get('webhook_id') and row.get('webhook_token'):
                    view = discord.ui.View(timeout=None)
                    for link in json.loads(row['links_json'] or '[]'):
                        view.add_item(discord.ui.Button(label=link['label'], url=link['url']))
                    async with aiohttp.ClientSession() as session:
                        webhook = discord.Webhook.partial(int(row['webhook_id']), row['webhook_token'], session=session)
                        if not self.card_registry.queued(destination, ident):
                            continue
                        target = '@original' if row.get('webhook_original') else int(ident)
                        options = {'view': view if view.children else None}
                        if self.card_registry.expired(destination, ident):
                            message = await asyncio.wait_for(webhook.fetch_message(target), timeout=10)
                            if not self.card_registry.queued(destination, ident):
                                continue
                            options['content'] = (message.content or '')[:1900] + '\n\nMenu expired. Use /help or /status to reopen.'
                        await asyncio.wait_for(webhook.edit_message(target, **options), timeout=10)
                    self.card_registry.finish(destination, ident)
                    continue
                channel = self.get_channel(int(destination)) or await self.fetch_channel(int(destination))
                message = await asyncio.wait_for(channel.fetch_message(int(ident)), timeout=10)
                if not self.card_registry.queued(destination, ident):
                    continue
                if message.author.id != self.user.id:
                    self.card_registry.finish(destination, ident)
                    continue
                options = edit_presentation('', [], message.components)
                edit = {'view': options['view']}
                if self.card_registry.expired(destination, ident):
                    edit['content'] = (getattr(message, 'content', '') or '')[:1900] + '\n\nMenu expired. Use /help or /status to reopen.'
                await asyncio.wait_for(message.edit(**edit), timeout=10)
                self.card_registry.finish(destination, ident)
            except discord.NotFound:
                self.card_registry.finish(destination, ident)
            except Exception as exc:
                self.card_registry.defer(destination, ident, time.time())
                log.warning('Related card cleanup deferred error_type=%s', type(exc).__name__)

    async def on_ready(self):
        log.info("Connected to Discord bot_id=%s mode=%s", self.user.id,
                 self.service.config.bot_mode)

    async def on_disconnect(self):
        log.warning("Discord disconnected; Gateway reconnect is enabled")

    async def on_resumed(self):
        log.info("Discord Gateway session resumed")

    async def on_error(self, event_method, *args, **kwargs):
        # Override discord.py's default traceback logging.
        log.error("Discord event handler failed event=%s", event_method)

    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = (interaction.data or {}).get('custom_id', '')
        if (self.card_registry is not None and getattr(interaction, 'message', None)
                and self.card_registry.expired(str(interaction.channel_id), str(interaction.message.id))):
            await interaction.response.send_message('This menu timed out. Open a new one with /help or /status.', ephemeral=True)
            await self.cleanup_cards()
            return
        if isinstance(custom_id, str) and custom_id.startswith('snake_menu:'):
            section = custom_id[len('snake_menu:'):]
            if section in NAVIGATION:
                try:
                    await self.menu_command(interaction, section)
                    if self.service.command_allowed(str(interaction.user.id), str(interaction.channel_id), interaction.guild_id):
                        self.renew_controls(interaction)
                except Exception as exc:
                    log.error('Menu navigation failed error_type=%s', type(exc).__name__)
                    if interaction.response.is_done():
                        await interaction.followup.send('⚠️ This menu could not be opened. Try its slash command.', ephemeral=True)
            return
        match = CUSTOM_ID.fullmatch((interaction.data or {}).get('custom_id', ''))
        if not match:
            return
        try:
            # Only n8n's successful ownership/claim check permits editing the card.
            await interaction.response.defer(thinking=False)
            reply = await self.service.handle_action(str(interaction.user.id),
                str(interaction.channel_id), str(interaction.guild_id) if interaction.guild_id else None,
                match[1], match[2])
            if getattr(reply, 'action_accepted', False):
                self.wake_notifications()
                self.renew_controls(interaction)
            if (getattr(reply, 'action_accepted', False)
                    and getattr(reply, 'preserve_original_controls', False)):
                sent = await interaction.followup.send(ephemeral=True, wait=True, **presentation(reply))
                self.remember_card(reply, sent, str(interaction.user.id), str(interaction.channel_id), interaction)
                return
            if (getattr(reply, 'action_accepted', False) or getattr(reply, 'clear_controls', False)) and interaction.message:
                if self.card_registry is not None:
                    try:
                        group = ('notice:' if match[2].startswith('notice_') else 'pending:') + match[1]
                        owner, destination = str(interaction.user.id), str(interaction.channel_id)
                        current = str(interaction.message.id)
                        self.card_registry.remember(group, destination, current, owner)
                        if getattr(reply, 'choices', None):
                            self.card_registry.link(group, 'pending:' + str(reply.pending_id), owner, destination)
                        self.card_registry.consume(group, owner, destination, current)
                        self.remember_card(reply, interaction.message, owner, destination)
                    except Exception as exc:
                        log.warning('Related card update deferred error_type=%s', type(exc).__name__)
                try:
                    await interaction.edit_original_response(
                        **edit_presentation(reply, interaction.message.embeds,
                            getattr(interaction.message, 'components', ())))
                except discord.HTTPException as exc:
                    log.warning('Confirmation card edit failed error_type=%s', type(exc).__name__)
                else:
                    if self.card_registry is not None and not getattr(reply, 'choices', None):
                        self.card_registry.finish(str(interaction.channel_id), str(interaction.message.id))
                    if (match[2].startswith(('notice_', 'ret'))
                            or getattr(reply, 'retention_updated', False)):
                        await interaction.followup.send(ephemeral=True, content=str(reply),
                            allowed_mentions=discord.AllowedMentions.none())
                        return
                    return
            sent = await interaction.followup.send(ephemeral=True, wait=True, **presentation(reply))
            self.remember_card(reply, sent, str(interaction.user.id), str(interaction.channel_id), interaction)
        except Exception as exc:
            log.error('Confirmation interaction failed error_type=%s', type(exc).__name__)

    async def on_message(self, message: discord.Message):
        if self.user is None or message.webhook_id is not None:
            return
        try:
            incoming = IncomingMessage(
                text=message.content, user_id=str(message.author.id),
                username=message.author.name, channel_id=str(message.channel.id),
                guild_id=str(message.guild.id) if message.guild else None,
                is_bot=message.author.bot,
                message_id=str(message.id),
                requested_at=discord.utils.snowflake_time(message.id).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            )
            response = await self.service.handle(incoming, str(self.user.id))
            if response is not None and self.service.command_allowed(incoming.user_id,
                    incoming.channel_id, message.guild.id if message.guild else None) and not incoming.is_bot:
                self.wake_notifications()
            if response is not None:
                if (getattr(response, 'choices', None) or getattr(response, 'jellyfin_url', None)
                        or getattr(response, 'notice_id', None) or getattr(response, 'local_jellyfin_url', None)):
                    options = presentation(response)
                    try:
                        sent = await message.reply(mention_author=False, **options)
                    except discord.Forbidden:
                        options.update(content=str(response), embed=None)
                        sent = await message.reply(mention_author=False, **options)
                    self.remember_card(response, sent, incoming.user_id, incoming.channel_id)
                    return
                poster = getattr(response, 'poster_url', None)
                if poster:
                    embed = discord.Embed(description=str(response), colour=0x2ECC71)
                    embed.set_thumbnail(url=poster)
                    try:
                        await message.reply(embed=embed, mention_author=False,
                                            allowed_mentions=discord.AllowedMentions.none())
                        return
                    except discord.Forbidden:
                        log.warning('Embed permission unavailable; using text reply')
                await message.reply(str(response), mention_author=False,
                                    allowed_mentions=discord.AllowedMentions.none())
        except Exception as exc:
            log.error("Discord message handling failed message_id=%s error_type=%s",
                      message.id, type(exc).__name__)
