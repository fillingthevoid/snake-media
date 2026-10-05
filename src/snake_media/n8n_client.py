"""HTTP transport and the versioned n8n response boundary; no media logic."""
import asyncio
import json
import logging
import re
import ipaddress
from urllib.parse import urlsplit

import aiohttp
from discord.utils import escape_markdown, escape_mentions

from .requests import MediaRequest

log = logging.getLogger('snake_media')
MAX_RESPONSE_BYTES = 65536


class N8NError(ValueError):
    """Safe error code only; never includes a URL or response body."""


class MediaReply(str):
    """Display text with optional presentation metadata; compatible with text replies."""
    def __new__(cls, text: str, poster_url=None, jellyfin_url=None, notice_id=None, local_jellyfin_url=None):
        reply = super().__new__(cls, text)
        reply.poster_url = None
        reply.jellyfin_url = None
        reply.local_jellyfin_url = None
        reply.notice_id = notice_id if isinstance(notice_id, str) and re.fullmatch(r'[1-9][0-9]{0,15}', notice_id) else None
        for field, candidate in [('jellyfin_url', jellyfin_url), ('local_jellyfin_url', local_jellyfin_url)]:
          if isinstance(candidate, str) and len(candidate) <= 2048:
            try:
                url = urlsplit(candidate)
                safe_http = False
                if url.scheme == 'http' and url.hostname and url.port == 8096:
                    safe_http = (url.hostname == '192.168.1.10' or
                                 ipaddress.ip_address(url.hostname) in ipaddress.ip_network('100.64.0.0/10'))
                if ((url.scheme == 'https' and url.hostname and url.port in (None, 443)
                         or safe_http)
                        and not url.username and not url.password
                        and url.path.endswith('/web/index.html') and '..' not in url.path.split('/')
                        and not any(c.isspace() or ord(c) < 32 for c in candidate) and not url.query
                        and re.fullmatch(r'!/details\?id=[A-Za-z0-9%_-]+', url.fragment)):
                    setattr(reply, field, candidate)
            except ValueError:
                pass
        if reply.local_jellyfin_url == reply.jellyfin_url:
            reply.local_jellyfin_url = None
        if isinstance(poster_url, str) and len(poster_url) <= 2048:
            try:
                url = urlsplit(poster_url)
                if (url.scheme == 'https' and url.hostname in
                        {'image.tmdb.org', 'artworks.thetvdb.com'}
                        and not url.username and not url.password
                        and url.port in (None, 443) and not url.query and not url.fragment
                        and not any(c.isspace() or ord(c) < 32 for c in poster_url)):
                    reply.poster_url = poster_url
            except ValueError:
                pass
        return reply


def format_result(data: object) -> str:
    if (not isinstance(data, dict) or type(data.get('version')) is not int
            or data['version'] != 1):
        raise N8NError('invalid_response_version')
    status = data.get('status')
    if status in ('confirmation', 'notice'):
        text = data.get('text')
        if not isinstance(text, str) or not 1 <= len(text) <= 1800:
            raise N8NError('invalid_confirmation_text')
        reply = MediaReply(escape_mentions(escape_markdown(text)), data.get('posterUrl'),
                           data.get('jellyfinUrl'), data.get('noticeId'), data.get('localJellyfinUrl'))
        reply.action_accepted = data.get('actionAccepted') is True
        reply.clear_controls = data.get('clearControls') is True and data.get('busy') is not True
        if status == 'confirmation':
            pending = data.get('pendingId')
            choices = data.get('choices')
            if (not isinstance(pending, str) or not re.fullmatch(r'[1-9][0-9]{0,15}', pending)
                    or not isinstance(choices, list) or not 1 <= len(choices) <= 25):
                raise N8NError('invalid_confirmation')
            for choice in choices:
                if (not isinstance(choice, dict) or not isinstance(choice.get('label'), str)
                        or not 1 <= len(choice['label']) <= 80
                        or not isinstance(choice.get('action'), str)
                        or not re.fullmatch(r'confirm|cancel|latest|all|choose|season_[1-9][0-9]{0,3}|page_[0-9]{1,3}|rettitle_[0-9]{1,4}|retpage_[0-9]{1,3}|retdays_(?:7|30)', choice['action'])):
                    raise N8NError('invalid_confirmation_choice')
            reply.pending_id, reply.choices = pending, choices
        return reply
    if status == 'clarification':
        return ("🤔 I couldn't confidently determine whether you meant a movie or TV show.\n\n"
                "Try: Movie: Add Step Brothers from 2008\nTV: Add Severance")
    if status == 'not_found':
        return '🔎 No matching title was found. Try including the release year.'
    if status == 'error':
        return "⚠️ Snake Media couldn't process that request right now. Please try again in a moment."
    if status not in ('added', 'already_added'):
        raise N8NError('invalid_response_status')
    media_type = data.get('mediaType')
    title = data.get('title')
    if media_type not in ('movie', 'tv') or not isinstance(title, str) or not title.strip():
        raise N8NError('invalid_media_result')
    title = escape_mentions(escape_markdown(' '.join(title.split())[:300]))
    icon, application = ('🎬', 'Radarr') if media_type == 'movie' else ('📺', 'Sonarr')
    if status == 'already_added':
        return MediaReply(f'{icon} {title}\n\n✅ Already in {application}.', data.get('posterUrl'))
    if type(data.get('searchStarted')) is not bool:
        raise N8NError('missing_search_confirmation')
    search = 'Search started.' if data['searchStarted'] else 'Search was not confirmed.'
    return MediaReply(f'{icon} {title}\n\n🔎 Added to {application}.\n{search}', data.get('posterUrl'))


class N8NClient:
    def __init__(self, url: str, secret: str, timeout_seconds: float = 60):
        self._url = url
        self._secret = secret
        self._timeout_seconds = timeout_seconds
        self._session = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._timeout_seconds, connect=5),
            connector=aiohttp.TCPConnector(limit=4),
            cookie_jar=aiohttp.DummyCookieJar(), trust_env=False,
            headers={'X-Snake-Media-Key': self._secret, 'Accept': 'application/json'},
        )
        return self

    async def __aexit__(self, *args):
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def submit(self, request: MediaRequest) -> str:
        return await self._post(request.to_payload())

    async def action(self, user_id, channel_id, guild_id, pending_id, action):
        return await self._post({'source': 'discord', 'userId': user_id,
            'channelId': channel_id, 'guildId': guild_id, 'pendingId': pending_id,
            'action': action, 'text': 'confirmation'})

    async def _post(self, payload) -> str:
        if self._session is None:
            raise N8NError('client_not_open')
        try:
            async with self._session.post(self._url, json=payload,
                                          allow_redirects=False) as response:
                if response.status != 200:
                    raise N8NError(f'http_status_{response.status}')
                if response.content_type != 'application/json':
                    raise N8NError('invalid_content_type')
                body = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise N8NError('response_too_large')
                try:
                    data = json.loads(body)
                except (ValueError, UnicodeError, RecursionError):
                    raise N8NError('invalid_json') from None
                result = format_result(data)
                if data['status'] == 'error':
                    log.error('n8n returned workflow error status')
                return result
        except asyncio.TimeoutError:
            log.error('n8n request timed out; outcome unknown; no retry')
            return ('⚠️ n8n may still be processing your request. '
                    'Check its outcome before submitting again.')
        except N8NError as exc:
            log.error('n8n communication failed code=%s', exc)
            raise
        except aiohttp.ClientError as exc:
            log.error('n8n transport failed error_type=%s', type(exc).__name__)
            raise N8NError('transport_error') from None
