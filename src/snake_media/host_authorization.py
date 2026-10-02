"""Host-only Unix-socket bridge. Never mount the bot's secret .env into Docker."""
import json
import os
import socket
import socketserver
import struct
import tempfile
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .admin_authorization import grant_users, replace_allowlist, valid_id
from .config import parse_ids


def read_env(path):
    result = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            if key.strip() in result:
                raise ValueError('duplicate_environment_key')
            result[key.strip()] = value.strip().strip('\"\'')
    return result


def atomic_write(path, text, mode):
    fd, temporary = tempfile.mkstemp(prefix='.authorization-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def synchronize(env_path, state_path, payload):
    env = read_env(env_path)
    users = grant_users(payload, parse_ids(env['ADMIN_DISCORD_USER_IDS'], 'owners'),
        parse_ids(env['ALLOWED_DISCORD_CHANNEL_IDS'], 'channels'),
        parse_ids(env['ALLOWED_DISCORD_USER_IDS'], 'users'))
    original = env_path.read_text()
    updated = replace_allowlist(original, users)
    target = urlsplit(env['N8N_WEBHOOK_URL'])
    url = urlunsplit((target.scheme, target.netloc, '/webhook/snake-discord-authorization', '', ''))
    req = urllib.request.Request(url, data=json.dumps(payload | {'users': users}).encode(),
        headers={'X-Snake-Media-Key': env['N8N_WEBHOOK_SECRET'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read(32769)
        if response.status != 200 or len(raw) > 32768:
            raise ValueError('backend_sync_failed')
        ack = json.loads(raw)
    confirmed = ack.get('users')
    if (ack.get('synchronized') is not True or not isinstance(confirmed, list)
            or not all(valid_id(x) for x in confirmed) or not set(users).issubset(confirmed)):
        raise ValueError('backend_sync_unconfirmed')
    users = sorted(set(confirmed), key=int)
    updated = replace_allowlist(original, users)
    # Persist only after n8n confirms. Retries set the same IDs and are idempotent.
    atomic_write(env_path, updated, 0o600)
    atomic_write(state_path, json.dumps({'version': 1, 'users': users}), 0o644)
    return {'version': 1, 'synchronized': True, 'userId': payload['user']}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        status, result = 503, {'version': 1, 'synchronized': False}
        try:
            uid = struct.unpack('3i', self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
            if uid != self.server.peer_uid or self.path != '/authorize':
                raise ValueError('invalid_peer')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('invalid_body')
            self.connection.settimeout(10)
            payload = json.loads(self.rfile.read(length))
            result = synchronize(self.server.env_path, self.server.state_path, payload)
            status = 200
        except Exception as exc:
            print('Authorization synchronization failed: ' + type(exc).__name__, flush=True)
        raw = json.dumps(result).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main():
    env_path = Path(os.environ['ADMIN_ENV_PATH'])
    state_path = Path(os.environ['ADMIN_STATE_PATH'])
    sock = Path(os.environ['ADMIN_SOCKET_PATH'])
    if sock.exists():
        sock.unlink()
    with socketserver.UnixStreamServer(str(sock), Handler) as server:
        server.env_path, server.state_path = env_path, state_path
        server.peer_uid = int(os.environ.get('ADMIN_PEER_UID', '10001'))
        # Access is checked with Linux peer credentials, independently of file permissions.
        os.chmod(sock, 0o666)
        server.serve_forever()


if __name__ == '__main__':
    main()
