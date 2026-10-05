"""Independent private Discord alerts for Snake Media host health."""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.error
import urllib.request

import alert_policy as policy
from alert_probes import health_facts, backup_probe, n8n_probe

LOG = logging.getLogger('snake-alerts')


def load_state(path):
    if not Path(path).exists():
        return {'schema': 1, 'issues': {}}
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict) or value.get('schema') != 1 or not isinstance(value.get('issues'), dict):
        raise ValueError('invalid_alert_state')
    return value


def save_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
            name = handle.name
            os.chmod(name, 0o600)
            json.dump(state, handle, ensure_ascii=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        name = None
    finally:
        if name:
            os.unlink(name)


def observations(snapshot, ops, backup, owner, users, issues, now):
    facts = health_facts(snapshot, now)
    facts.update(backup=backup, lock=ops['lock'], **{'monitor:metadata': ops['available'] and ops['lock'] is not None})
    recipients = {key: [owner] for key in facts}
    titles = {}
    for identifier, request in ops['requests'].items():
        user = request['userId']
        if user not in users:
            continue
        key = 'request:' + identifier
        facts[key] = request['healthy']
        recipients[key] = [owner]
        titles[key] = request['title']
    # A missing database or pruned record cannot establish a recovery.
    for row in issues.values():
        key, user = row['key'], row['recipient']
        if key.startswith('request:') and key not in facts:
            facts[key] = None
            recipients[key] = [owner]
    return facts, recipients, titles


LABELS = {'backup': 'Encrypted server backup is failed or overdue.',
          'lock': 'Media requests may be blocked by a stalled operation.',
          'storage:mounts': 'The media storage mount check failed.',
          'storage:space': 'Combined media storage has less than 50 GiB free.',
          'playback:sample': 'The Jellyfin media streaming check failed.',
          'monitor:health': 'Server health readings are unavailable or stale.',
          'monitor:metadata': 'Media request health could not be checked.'}


def render(events, titles):
    lines = ['Snake Media server update']
    for event in events:
        key = event['key']
        recovery = event['kind'] == 'recovery'
        if key.startswith('request:'):
            title = titles.get(key, 'Your request')
            text = (title + ': no longer appears stuck. Check /status for its current progress.' if recovery
                    else title + ': confirmation is taking longer than expected. Check /status before submitting it again.')
        elif key.startswith('service:'):
            text = key.split(':', 1)[1] + (' is reachable again.' if recovery else ' is not responding.')
        else:
            text = (key.replace(':', ' ') + ': check is healthy again.' if recovery else LABELS.get(key, 'A server check failed.'))
        lines.append(('✅ ' if recovery else '⚠️ ') + text)
    return '\n\n'.join(lines)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class DeliveryDeferred(Exception):
    def __init__(self, seconds):
        self.seconds = seconds


class DiscordSender:
    def __init__(self, token):
        self.token = token
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def post(self, path, body):
        request = urllib.request.Request('https://discord.com/api/v10' + path,
            data=json.dumps(body).encode(), headers={'Authorization': 'Bot ' + self.token,
            'Content-Type': 'application/json', 'User-Agent': 'SnakeMediaAlerts/1.0'}, method='POST')
        try:
            with self.opener.open(request, timeout=15) as response:
                payload = response.read(65537)
                if len(payload) > 65536:
                    raise ValueError('oversized_response')
                return json.loads(payload)
        except urllib.error.HTTPError as error:
            if error.code == 403:
                raise DeliveryDeferred(4 * 3600) from None
            if error.code == 429:
                try:
                    delay = float(json.loads(error.read(65536)).get('retry_after', 300))
                except Exception:
                    delay = 300
                raise DeliveryDeferred(min(86400, max(300, delay))) from None
            raise DeliveryDeferred(300) from None

    def send(self, recipient, content, nonce):
        if not re.fullmatch(r'[0-9]{1,20}', recipient) or len(content) > 1900 or len(nonce) > 25:
            raise ValueError('invalid_message')
        channel = self.post('/users/@me/channels', {'recipient_id': recipient})
        if channel.get('type') != 1 or [u.get('id') for u in channel.get('recipients', [])] != [recipient]:
            raise ValueError('unexpected_dm_recipient')
        identifier = channel.get('id', '')
        if not re.fullmatch(r'[0-9]{1,20}', identifier):
            raise ValueError('invalid_dm_channel')
        message = self.post('/channels/' + identifier + '/messages', {'content': content,
            'nonce': nonce, 'enforce_nonce': True, 'allowed_mentions': {'parse': []}})
        if not message.get('id') or message.get('channel_id') != identifier or str(message.get('nonce')) != nonce:
            raise ValueError('unverified_delivery')
        return message['id']


def deliver_events(sender, path, state, events, titles, now):
    save_state(path, state)
    sent = deferred = 0
    delays = state.setdefault('retryAfter', {})
    # One event per message keeps retries stable even when other issues change.
    for event in events:
        recipient = event['recipient']
        if delays.get(recipient, 0) > now:
            deferred += 1
            continue
        try:
            sender.send(recipient, render([event], titles), event['id'])
        except Exception as error:
            delays[recipient] = now + (error.seconds if isinstance(error, DeliveryDeferred) else 300)
            LOG.warning('Private alert delivery deferred (%s)', type(error).__name__)
            deferred += 1
        else:
            policy.delivered(state['issues'], event, now)
            delays.pop(recipient, None)
            sent += 1
        save_state(path, state)
    return sent, deferred


def read_env(path):
    values = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip('"\'')
    return values


def health_snapshot(path):
    try:
        config = json.loads(Path(path).read_text(encoding='utf-8'))
        import ipaddress
        address = ipaddress.ip_address(config['bind'])
        if not address.is_private or address.version != 4:
            raise ValueError('invalid_health_address')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        request = urllib.request.Request('http://' + str(address) + ':' + str(int(config['port'])) + '/health',
            headers={'X-Snake-Media-Key': config['secret']})
        with opener.open(request, timeout=25) as response:
            payload = response.read(1048577)
            if len(payload) > 1048576:
                raise ValueError('oversized_health')
            return json.loads(payload)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('env-file', 'health-config', 'database', 'backup-dir', 'state'):
        parser.add_argument('--' + option, required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--test-dm', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    env = read_env(args.env_file)
    owner = env.get('ALERT_OWNER_DISCORD_USER_ID', '')
    admins = {s.strip() for s in env.get('ADMIN_DISCORD_USER_IDS', '').split(',')}
    users = {s.strip() for s in env.get('ALLOWED_DISCORD_USER_IDS', '').split(',') if re.fullmatch(r'[0-9]{1,20}', s.strip())}
    if not re.fullmatch(r'[0-9]{17,20}', owner) or owner not in admins or not env.get('DISCORD_TOKEN'):
        raise ValueError('invalid_private_alert_configuration')
    sender = DiscordSender(env['DISCORD_TOKEN'])
    if args.test_dm:
        sender.send(owner, '✅ Snake Media server alerts are connected. This is a test message.', str(time.time_ns())[:24])
        LOG.info('Owner test DM delivered')
        return
    import fcntl
    path = Path(args.state)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(str(path) + '.lock', 'a') as handle:
        os.chmod(handle.name, 0o600)
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = load_state(path)
        now = time.time()
        ops = n8n_probe(args.database, now, users)
        facts, recipients, titles = observations(health_snapshot(args.health_config), ops,
            backup_probe(args.backup_dir, now), owner, users, state['issues'], now)
        events = policy.observe(state['issues'], facts, recipients, now)
        if args.dry_run:
            LOG.info('Dry run: %s healthy, %s unhealthy, %s unknown; %s eligible alerts',
                sum(v is True for v in facts.values()), sum(v is False for v in facts.values()),
                sum(v is None for v in facts.values()), len(events))
            return
        sent, deferred = deliver_events(sender, path, state, events, titles, now)
        LOG.info('Checks completed; %s alerts delivered, %s deferred', sent, deferred)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        LOG.error('Alert monitor stopped safely (%s)', type(error).__name__)
        raise SystemExit(1)
