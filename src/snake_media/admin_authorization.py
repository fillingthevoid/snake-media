"""Discord access configuration only. Media decisions remain in n8n."""
import json
import re
from pathlib import Path


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r'[1-9][0-9]{0,19}', value) and int(value) < 2**64


class LiveUsers:
    def __init__(self, initial, path=''):
        self.initial, self.path = frozenset(initial), path

    def snapshot(self):
        if not self.path:
            return self.initial
        try:
            raw = Path(self.path).read_bytes()
            if len(raw) > 32768:
                return frozenset()
            data = json.loads(raw)
            ids = data.get('users')
            if data.get('version') != 1 or not isinstance(ids, list) or not ids or not all(valid_id(x) for x in ids):
                return frozenset()
            return frozenset(ids)
        except FileNotFoundError:
            return self.initial
        except (OSError, ValueError, TypeError, AttributeError):
            return frozenset()

    def __contains__(self, user):
        return user in self.snapshot()


def grant_users(payload, owners, channels, existing):
    if (not isinstance(payload, dict) or payload.get('actor') not in owners
            or payload.get('channel') not in channels or not valid_id(payload.get('guild'))
            or not valid_id(payload.get('user'))):
        raise ValueError('authorization_denied')
    return sorted(set(existing) | set(owners) | {payload['user']}, key=int)


def replace_allowlist(text, users):
    if not users or not all(valid_id(x) for x in users):
        raise ValueError('invalid_users')
    lines = text.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if re.match(r'^\s*ALLOWED_DISCORD_USER_IDS\s*=', line)]
    if len(matches) != 1:
        raise ValueError('ambiguous_allowlist')
    i = matches[0]
    ending = '\r\n' if lines[i].endswith('\r\n') else '\n' if lines[i].endswith('\n') else ''
    lines[i] = 'ALLOWED_DISCORD_USER_IDS=' + ','.join(sorted(set(users), key=int)) + ending
    return ''.join(lines)


class AdminClient:
    def __init__(self, socket_path):
        self.socket_path = socket_path

    async def authorize(self, actor, channel, guild, user):
        import aiohttp
        async with aiohttp.ClientSession(connector=aiohttp.UnixConnector(path=self.socket_path),
                timeout=aiohttp.ClientTimeout(total=30), trust_env=False) as session:
            async with session.post('http://localhost/authorize', json={
                    'actor': actor, 'channel': channel, 'guild': guild, 'user': user}) as response:
                raw = await response.content.read(4097)
                if response.status != 200 or len(raw) > 4096:
                    raise ValueError('authorization_sync_failed')
                data = json.loads(raw)
                if data.get('version') != 1 or data.get('synchronized') is not True:
                    raise ValueError('authorization_sync_unconfirmed')
                return data
