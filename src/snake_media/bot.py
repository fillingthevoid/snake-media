import logging
import asyncio

import discord
from discord import app_commands

from .requests import IncomingMessage
from .service import RequestService
from .notifications import NotificationDelivery
from .confirmations import CUSTOM_ID, presentation, edit_presentation, notification_view
from .n8n_client import MediaReply

log = logging.getLogger("snake_media")


class SnakeMediaClient(discord.Client):
    def __init__(self, service: RequestService, notification_transport=None, notification_journal=None):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(intents=intents, max_messages=None,
                         allowed_mentions=discord.AllowedMentions.none())
        self.service = service
        self.notification_task = None
        self.notification_transport = notification_transport
        self.notification_journal = notification_journal
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(app_commands.Command(name='authorize',
            description='Owner only: authorize a Discord account in Snake Media.',
            callback=self.authorize_command))
        self.tree.add_command(app_commands.Command(name='status',
            description='Show your media requests, download progress and expiry.',
            callback=self.status_command))

    async def authorize_command(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        reply = await self.service.authorize_user(str(interaction.user.id),
            str(interaction.channel_id), str(interaction.guild_id) if interaction.guild_id else None,
            user_id.strip())
        await interaction.followup.send(reply, ephemeral=True,
                                       allowed_mentions=discord.AllowedMentions.none())

    async def status_command(self, interaction: discord.Interaction, title: str = ''):
        await interaction.response.defer(ephemeral=True, thinking=True)
        incoming = IncomingMessage(text=f'<@{self.user.id}> status {title}',
            user_id=str(interaction.user.id), username=interaction.user.name,
            channel_id=str(interaction.channel_id),
            guild_id=str(interaction.guild_id) if interaction.guild_id else None,
            is_bot=False, message_id=str(interaction.id))
        reply = await self.service.handle(incoming, str(self.user.id))
        await interaction.followup.send(ephemeral=True,
            **presentation(reply or 'Use Snake Media in an authorized server channel.'))

    async def setup_hook(self):
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
            self.notification_task = asyncio.create_task(worker.run(self))

    async def send_notification(self, channel_id, message_id, text, notice_id=None,
                                poster_url=None, jellyfin_url=None, local_jellyfin_url=None):
        channel = self.get_channel(int(channel_id)) or await self.fetch_channel(int(channel_id))
        reference = discord.MessageReference(message_id=int(message_id), channel_id=int(channel_id),
                                             fail_if_not_exists=False)
        reply = MediaReply(discord.utils.escape_mentions(discord.utils.escape_markdown(text)),
                           poster_url, jellyfin_url, notice_id, local_jellyfin_url)
        options = presentation(reply)
        options.setdefault('view', None)
        message = await channel.send(reference=reference, **options)
        log.info('Completion notice delivered channel_id=%s', channel_id)
        return str(message.id)

    async def close(self):
        if self.notification_task:
            self.notification_task.cancel()
            await asyncio.gather(self.notification_task, return_exceptions=True)
        await super().close()

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
        match = CUSTOM_ID.fullmatch((interaction.data or {}).get('custom_id', ''))
        if not match:
            return
        try:
            # Only n8n's successful ownership/claim check permits editing the card.
            await interaction.response.defer(ephemeral=True, thinking=True)
            reply = await self.service.handle_action(str(interaction.user.id),
                str(interaction.channel_id), str(interaction.guild_id) if interaction.guild_id else None,
                match[1], match[2])
            if (getattr(reply, 'action_accepted', False) or getattr(reply, 'clear_controls', False)) and interaction.message:
                try:
                    await interaction.message.edit(
                        **edit_presentation(reply, interaction.message.embeds))
                except discord.HTTPException as exc:
                    log.warning('Confirmation card edit failed error_type=%s', type(exc).__name__)
                else:
                    try:
                        await interaction.delete_original_response()
                    except discord.HTTPException:
                        log.warning('Confirmation acknowledgement cleanup failed')
                    return
            await interaction.followup.send(ephemeral=True, **presentation(reply))
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
            if response is not None:
                if (getattr(response, 'choices', None) or getattr(response, 'jellyfin_url', None)
                        or getattr(response, 'notice_id', None) or getattr(response, 'local_jellyfin_url', None)):
                    options = presentation(response)
                    try:
                        await message.reply(mention_author=False, **options)
                    except discord.Forbidden:
                        options.update(content=str(response), embed=None)
                        await message.reply(mention_author=False, **options)
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
