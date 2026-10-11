"""Regression tests for stalled authorization and exhausted card cleanup."""
import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from snake_media.host_authorization import Handler
from snake_media.card_registry import CardRegistry


class PeerSocket:
    """Real socket I/O with a portable substitute for Linux peer credentials."""
    def __init__(self, connection, uid):
        self.connection, self.uid = connection, uid

    def getsockopt(self, *args):
        if self.uid is None:
            raise OSError('peer credentials unavailable')
        return struct.pack('3i', 1, self.uid, 1)

    def settimeout(self, seconds):
        self.connection.settimeout(min(seconds, 0.05))

    def __getattr__(self, name):
        return getattr(self.connection, name)


class AuthorizationRecoveryTests(unittest.TestCase):
    def run_connection(self, uid, request):
        server, client = socket.socketpair()
        errors = []
        def handle():
            try:
                Handler(PeerSocket(server, uid), ('local', 0), SimpleNamespace(
                    peer_uid=10001, env_path=Path('unused.env'), state_path=Path('unused.json')))
            except Exception as exc:
                errors.append(exc)
        with patch.object(socket, 'SO_PEERCRED', 17, create=True):
            thread = threading.Thread(target=handle, daemon=True)
            thread.start()
            try:
                if request:
                    client.sendall(request)
                thread.join(0.5)
                completed = not thread.is_alive()
                server.shutdown(socket.SHUT_WR)
                client.settimeout(0.5)
                response = b''
                while True:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    response += chunk
            finally:
                client.close()
                thread.join(1)
                server.close()
        if completed:
            self.assertFalse(errors)
        return completed, response

    def test_incomplete_headers_release_the_handler(self):
        completed, _ = self.run_connection(10001, b'POST /authorize HTTP/1.1\r\nHost: localhost\r\n')
        self.assertTrue(completed)

    def test_wrong_peer_is_rejected_without_waiting_for_http(self):
        completed, response = self.run_connection(12345, b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        self.assertTrue(completed)
        self.assertEqual(response, b'')

    def test_peer_lookup_failure_rejects_connection(self):
        completed, response = self.run_connection(None, b'GET / HTTP/1.1\r\n\r\n')
        self.assertTrue(completed)
        self.assertEqual(response, b'')

    def test_authorized_complete_request_still_returns_success(self):
        with patch('snake_media.host_authorization.synchronize', return_value={'version': 1, 'synchronized': True}):
            completed, response = self.run_connection(10001,
                b'POST /authorize HTTP/1.1\r\nContent-Length: 2\r\n\r\n{}')
        self.assertTrue(completed)
        self.assertIn(b'200 OK', response)
        self.assertIn(b'"synchronized": true', response)


class CleanupRecoveryTests(unittest.TestCase):
    def test_cleanup_recovers_after_twelve_failures_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cards.sqlite3'
            with CardRegistry(path) as cards:
                cards.track('1', '2', '3', now=0)
                cards.expire(301)
                now = 301
                for _ in range(12):
                    self.assertTrue(cards.pending(now))
                    cards.defer('1', '2', now)
                    now = cards.connection.execute('SELECT retry_at FROM cleanup').fetchone()[0]
            with CardRegistry(path) as cards:
                cards.expire(now)
                self.assertEqual([r['message_id'] for r in cards.pending(now)], ['2'])
                cards.finish('1', '2')
                self.assertFalse(cards.queued('1', '2'))
                self.assertIsNone(cards.control('1', '2'))

    def test_legacy_exhausted_jobs_resume_with_bounded_backoff(self):
        with tempfile.TemporaryDirectory() as folder, CardRegistry(Path(folder) / 'cards.sqlite3') as cards:
            cards.track('1', '2', '3', now=0)
            cards.expire(301)
            cards.connection.execute('UPDATE cleanup SET attempts=12')
            self.assertTrue(cards.pending(301))
            for now in range(301, 100301, 1000):
                cards.defer('1', '2', now)
                row = cards.connection.execute('SELECT attempts,retry_at FROM cleanup').fetchone()
                self.assertLessEqual(row['attempts'], 5)
                self.assertGreaterEqual(row['retry_at'] - now, 300)
                self.assertLessEqual(row['retry_at'] - now, 3600)

    def test_compaction_retires_old_failed_controls_but_keeps_recent_jobs(self):
        with tempfile.TemporaryDirectory() as folder, CardRegistry(Path(folder) / 'cards.sqlite3') as cards:
            cards.remember('pending:1', '1', '2', '3')
            cards.track('1', '2', '3', now=0)
            cards.track('1', '4', '3', now=1000)
            cards.expire(2000)
            cards.compact(1000)
            self.assertFalse(cards.queued('1', '2'))
            self.assertIsNone(cards.control('1', '2'))
            self.assertEqual(cards.connection.execute('SELECT count(*) FROM cards').fetchone()[0], 0)
            self.assertTrue(cards.queued('1', '4'))
            self.assertIsNotNone(cards.control('1', '4'))
