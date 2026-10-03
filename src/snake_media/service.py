import logging
import re

from .authorization import is_authorized
from .config import Config
from .requests import IncomingMessage, MediaRequest, RequestBackend
from .admin_authorization import LiveUsers, AdminClient, valid_id

log = logging.getLogger("snake_media")
ERROR_REPLY = "⚠️ Snake Media couldn't process that request right now.\nPlease try again in a moment."


class TestBackend:
    async def submit(self, request: MediaRequest) -> str:
        return ("✅ Snake Media is connected and your account is authorized.\n"
                "Phase 1 test only. No media request was submitted to n8n.")


class RequestService:
    def __init__(self, config: Config, backend: RequestBackend):
        self.config = config
        self.backend = backend
        self.allowed_users = LiveUsers(config.allowed_user_ids, config.authorization_state_path)

    def command_allowed(self, user_id, channel_id, guild_id):
        return bool(guild_id and channel_id in self.config.allowed_channel_ids
                    and is_authorized(user_id, self.allowed_users))

    async def authorize_user(self, actor, channel, guild, user):
        if (actor not in self.config.admin_user_ids or channel not in self.config.allowed_channel_ids
                or not valid_id(guild)):
            return '⛔ Only the Snake Media owner can authorize users in this channel.'
        if not valid_id(user):
            return 'Enter a valid Discord user ID using digits only.'
        if not self.config.admin_socket_path:
            return '⚠️ User administration is not configured.'
        try:
            await AdminClient(self.config.admin_socket_path).authorize(actor, channel, guild, user)
            if user not in self.allowed_users:
                raise ValueError('local_sync_unconfirmed')
            log.info('Discord account authorized actor_id=%s user_id=%s', actor, user)
            return '✅ Account authorized in Discord and n8n. They can submit requests now.'
        except Exception as exc:
            log.error('Authorization synchronization failed error_type=%s', type(exc).__name__)
            return '⚠️ Authorization could not be confirmed in both services. Retry the command; duplicate IDs are safe.'

    async def handle_action(self, user_id, channel_id, guild_id, pending_id, action):
        if (not guild_id or channel_id not in self.config.allowed_channel_ids
                or not is_authorized(user_id, self.allowed_users)):
            return "⛔ This Discord account isn't authorized to use Snake Media here."
        try:
            return await self.backend.action(user_id, channel_id, guild_id, pending_id, action)
        except Exception as exc:
            log.error('Confirmation request failed error_type=%s', type(exc).__name__)
            return ERROR_REPLY

    async def handle(self, message: IncomingMessage, bot_id: str) -> str | None:
        if (message.is_bot or message.guild_id is None
                or message.channel_id not in self.config.allowed_channel_ids):
            return None
        mention = re.compile(r"<@!?" + re.escape(bot_id) + r">")
        if not mention.search(message.text):
            return None
        if not is_authorized(message.user_id, self.allowed_users):
            return "⛔ This Discord account isn't authorized to use Snake Media."
        text = mention.sub("", message.text).strip()
        if not text:
            return "Mention me with a request, such as: @Snake Media add The Matrix from 1999"
        if len(text) > 2000:
            return "Please keep your media request under 2,001 characters."
        request = MediaRequest(text, message.user_id, message.username,
                               message.channel_id, message.guild_id,
                               message.message_id, message.requested_at)
        try:
            return await self.backend.submit(request)
        except Exception as exc:
            # Deliberately omit arbitrary exception text, URLs and payloads.
            log.error("Backend request failed error_type=%s", type(exc).__name__)
            return ERROR_REPLY
