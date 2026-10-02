import os
import re
import math
from urllib.parse import urlsplit
from dataclasses import dataclass, field
from collections.abc import Mapping


class ConfigError(ValueError):
    """Invalid environment configuration; messages never include values."""


def parse_ids(value: str, name: str) -> frozenset[str]:
    parts = [part.strip() for part in value.split(",")]
    if any(not re.fullmatch(r"[1-9][0-9]{0,19}", part)
           or int(part) >= 2**64 for part in parts):
        raise ConfigError(f"{name} must contain comma-separated Discord IDs")
    return frozenset(parts)


@dataclass(frozen=True)
class Config:
    discord_token: str = field(repr=False)
    allowed_user_ids: frozenset[str]
    allowed_channel_ids: frozenset[str]
    n8n_webhook_url: str = field(default="", repr=False)
    bot_mode: str = 'test'
    n8n_webhook_secret: str = field(default='', repr=False)
    n8n_timeout_seconds: float = 60
    n8n_notifications_url: str = field(default='', repr=False)
    notification_state_path: str = '/state/notifications.sqlite3'
    admin_user_ids: frozenset[str] = field(default_factory=frozenset)
    admin_socket_path: str = ''
    authorization_state_path: str = ''

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        values = os.environ if env is None else env
        token = values.get("DISCORD_TOKEN", "").strip()
        if not token:
            raise ConfigError("DISCORD_TOKEN is required")
        mode = values.get('BOT_MODE', 'test').strip()
        if mode not in ('test', 'n8n'):
            raise ConfigError('BOT_MODE must be test or n8n')
        url = values.get('N8N_WEBHOOK_URL', '').strip()
        secret = values.get('N8N_WEBHOOK_SECRET', '').strip()
        notifications_url = values.get('N8N_NOTIFICATIONS_URL', '').strip()
        if notifications_url:
            try:
                target = urlsplit(notifications_url)
                valid_notifications = (target.scheme in ('http','https') and target.hostname
                    and not target.username and not target.password and not target.fragment
                    and target.port != 0 and not any(c.isspace() for c in notifications_url))
            except ValueError:
                valid_notifications = False
            if not valid_notifications:
                raise ConfigError('N8N_NOTIFICATIONS_URL must be HTTP(S) without userinfo or fragment')
        try:
            timeout = float(values.get('N8N_TIMEOUT_SECONDS', '60'))
        except ValueError:
            raise ConfigError('N8N_TIMEOUT_SECONDS must be a number from 1 to 120') from None
        if not math.isfinite(timeout) or not 1 <= timeout <= 120:
            raise ConfigError('N8N_TIMEOUT_SECONDS must be a number from 1 to 120')
        if mode == 'n8n':
            try:
                parsed = urlsplit(url)
                valid = (parsed.scheme in ('http', 'https') and parsed.hostname
                         and not parsed.username and not parsed.password
                         and not parsed.fragment and parsed.port != 0
                         and not any(char.isspace() for char in url))
            except ValueError:
                valid = False
            if not valid:
                raise ConfigError('N8N_WEBHOOK_URL must be HTTP(S) without userinfo or fragment')
            if not secret or any(ord(char) < 33 or ord(char) > 126 for char in secret):
                raise ConfigError('N8N_WEBHOOK_SECRET must be a nonempty printable ASCII header value')
        return cls(
            discord_token=token,
            allowed_user_ids=parse_ids(values.get("ALLOWED_DISCORD_USER_IDS", ""),
                                       "ALLOWED_DISCORD_USER_IDS"),
            allowed_channel_ids=parse_ids(values.get("ALLOWED_DISCORD_CHANNEL_IDS", ""),
                                          "ALLOWED_DISCORD_CHANNEL_IDS"),
            n8n_webhook_url=url, bot_mode=mode, n8n_webhook_secret=secret,
            n8n_timeout_seconds=timeout,
            n8n_notifications_url=notifications_url,
            notification_state_path=values.get('NOTIFICATION_STATE_PATH', '/state/notifications.sqlite3'),
            admin_user_ids=(parse_ids(values['ADMIN_DISCORD_USER_IDS'], 'ADMIN_DISCORD_USER_IDS')
                            if values.get('ADMIN_DISCORD_USER_IDS') else frozenset()),
            admin_socket_path=values.get('ADMIN_SOCKET_PATH', ''),
            authorization_state_path=values.get('AUTHORIZATION_STATE_PATH', ''),
        )
