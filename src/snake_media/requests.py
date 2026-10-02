from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class IncomingMessage:
    text: str
    user_id: str
    username: str
    channel_id: str
    guild_id: str | None
    is_bot: bool
    message_id: str = ''
    requested_at: str = ''


@dataclass(frozen=True)
class MediaRequest:
    text: str
    user_id: str
    username: str
    channel_id: str
    guild_id: str
    message_id: str = ''
    requested_at: str = ''

    def to_payload(self) -> dict[str, str]:
        payload = {"source": "discord", "text": self.text, "userId": self.user_id,
                "username": self.username, "channelId": self.channel_id,
                "guildId": self.guild_id}
        if self.message_id and self.requested_at:
            payload.update(messageId=self.message_id, requestedAt=self.requested_at)
        return payload


class RequestBackend(Protocol):
    async def submit(self, request: MediaRequest) -> str:
        """Return display text; n8n response decoding belongs behind this interface."""
        ...
