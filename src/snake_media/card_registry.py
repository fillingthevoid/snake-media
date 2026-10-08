"""Durable transport-only references to related public Discord cards."""
import re
import json
import os
import sqlite3
import time


class CardRegistry:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        os.chmod(path, 0o600)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('CREATE TABLE IF NOT EXISTS cards (group_key TEXT, destination_id TEXT, '
                                'message_id TEXT, owner_id TEXT, PRIMARY KEY(group_key,destination_id,message_id))')
        self.connection.execute('CREATE TABLE IF NOT EXISTS links (first_key TEXT, second_key TEXT, '
                                'owner_id TEXT, destination_id TEXT, PRIMARY KEY(first_key,second_key,owner_id,destination_id))')
        self.connection.execute('CREATE TABLE IF NOT EXISTS cleanup (destination_id TEXT, message_id TEXT, '
                                'retry_at REAL NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, '
                                'PRIMARY KEY(destination_id,message_id))')
        self.connection.execute('CREATE TABLE IF NOT EXISTS request_cards (destination_id TEXT, source_message_id TEXT, '
                                'message_id TEXT, owner_id TEXT, created_at REAL, '
                                'PRIMARY KEY(destination_id,source_message_id,owner_id))')
        if 'created_at' not in {r[1] for r in self.connection.execute('PRAGMA table_info(cards)')}:
            self.connection.execute('ALTER TABLE cards ADD COLUMN created_at REAL')
        self.connection.execute('UPDATE cards SET created_at=? WHERE created_at IS NULL', (time.time(),))
        self.connection.execute('CREATE TABLE IF NOT EXISTS controls (destination_id TEXT, message_id TEXT, '
                                'owner_id TEXT, expires_at REAL, webhook_id TEXT, webhook_token TEXT, links_json TEXT, '
                                'PRIMARY KEY(destination_id,message_id))')
        if 'webhook_original' not in {r[1] for r in self.connection.execute('PRAGMA table_info(controls)')}:
            self.connection.execute('ALTER TABLE controls ADD COLUMN webhook_original INTEGER NOT NULL DEFAULT 0')
        self.connection.execute('INSERT OR IGNORE INTO controls(destination_id,message_id,owner_id,expires_at,webhook_id,webhook_token,links_json) SELECT destination_id,message_id,owner_id, '
                                'MIN(created_at)+300,NULL,NULL,\'[]\' FROM cards GROUP BY destination_id,message_id')
        self.connection.commit()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    @staticmethod
    def valid(group, destination, message, owner):
        if not re.fullmatch(r'(?:notice|pending):[1-9][0-9]{0,15}', group) or any(
                not isinstance(v, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', v)
                for v in [destination, message, owner]):
            raise ValueError('invalid_card_reference')

    def remember(self, group, destination, message, owner):
        self.valid(group, destination, message, owner)
        with self.connection:
            existing = self.connection.execute('SELECT owner_id FROM cards WHERE group_key=? AND destination_id=? AND message_id=?',
                                               (group, destination, message)).fetchone()
            if existing and existing[0] != owner:
                raise ValueError('card_owner_conflict')
            self.connection.execute('INSERT OR IGNORE INTO cards VALUES (?,?,?,?,?)', (group, destination, message, owner, time.time()))
            self.connection.execute('DELETE FROM cleanup WHERE destination_id=? AND message_id=?', (destination, message))

    def link(self, first, second, owner, destination):
        self.valid(first, destination, '1', owner)
        self.valid(second, destination, '1', owner)
        with self.connection:
            self.connection.execute('INSERT OR IGNORE INTO links VALUES (?,?,?,?)', (first, second, owner, destination))

    def control(self, destination, message):
        row = self.connection.execute('SELECT * FROM controls WHERE destination_id=? AND message_id=?',
                                      (destination, message)).fetchone()
        return dict(row) if row else None

    def track(self, destination, message, owner, now=None, links=(), webhook_id=None, webhook_token=None):
        self.valid('pending:1', destination, message, owner)
        old = self.control(destination, message)
        if old and old['owner_id'] != owner:
            raise ValueError('card_owner_conflict')
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO controls VALUES (?,?,?,?,?,?,?,?)',
                (destination, message, owner, (time.time() if now is None else now) + 300,
                 webhook_id or (old or {}).get('webhook_id'),
                 webhook_token or (old or {}).get('webhook_token'), json.dumps(list(links)), (old or {}).get('webhook_original', 0)))
            self.connection.execute('DELETE FROM cleanup WHERE destination_id=? AND message_id=?', (destination, message))

    def expired(self, destination, message, now=None):
        row = self.control(destination, message)
        return bool(row and row['expires_at'] <= (time.time() if now is None else now))

    def touch(self, destination, message, owner, now=None, webhook_id=None, webhook_token=None):
        now = time.time() if now is None else now
        with self.connection:
            changed = self.connection.execute('UPDATE controls SET expires_at=? WHERE destination_id=? '
                'AND message_id=? AND owner_id=? AND expires_at>?', (now + 300, destination, message, owner, now)).rowcount
            if changed and webhook_token:
                self.connection.execute('UPDATE controls SET webhook_id=?,webhook_token=?,webhook_original=1 WHERE destination_id=? AND message_id=?',
                                        (webhook_id, webhook_token, destination, message))
        return bool(changed)

    def expire(self, now):
        with self.connection:
            self.connection.execute('INSERT OR IGNORE INTO cleanup(destination_id,message_id) '
                                    'SELECT destination_id,message_id FROM controls WHERE expires_at<=?', (now,))

    def remember_request(self, destination, source_message, message, owner):
        self.valid('pending:1', destination, message, owner)
        self.valid('pending:1', destination, source_message, owner)
        with self.connection:
            self.connection.execute('INSERT OR IGNORE INTO request_cards VALUES (?,?,?,?,?)',
                                    (destination, source_message, message, owner, time.time()))

    def request_card(self, destination, source_message, owner):
        row = self.connection.execute('SELECT message_id FROM request_cards WHERE destination_id=? '
                                      'AND source_message_id=? AND owner_id=?',
                                      (destination, source_message, owner)).fetchone()
        return row[0] if row else None

    def consume(self, group, owner, destination, current_message):
        self.valid(group, destination, current_message, owner)
        groups = {group}
        links = self.connection.execute('SELECT first_key,second_key FROM links WHERE owner_id=? AND destination_id=?',
                                        (owner, destination)).fetchall()
        for _ in range(len(links) + 1):
            old = len(groups)
            for a, b in links:
                if a in groups or b in groups:
                    groups.update([a, b])
            if len(groups) == old:
                break
        count = 0
        with self.connection:
            for key in groups:
                rows = self.connection.execute('SELECT message_id FROM cards WHERE group_key=? AND owner_id=? '
                                               'AND destination_id=? AND message_id!=?', (key, owner, destination, current_message)).fetchall()
                for row in rows:
                    count += self.connection.execute('INSERT OR IGNORE INTO cleanup(destination_id,message_id) VALUES (?,?)',
                                                     (destination, row[0])).rowcount
                self.connection.execute('DELETE FROM cards WHERE group_key=? AND owner_id=? AND destination_id=? '
                                        'AND message_id!=?', (key, owner, destination, current_message))
        return count

    def pending(self, now, limit=5):
        return [dict(r) for r in self.connection.execute('SELECT cleanup.*,controls.webhook_id,controls.webhook_token,controls.links_json,controls.webhook_original '
            'FROM cleanup LEFT JOIN controls USING(destination_id,message_id) '
            'WHERE retry_at<=? AND attempts<12 ORDER BY retry_at LIMIT ?', (now, min(limit, 5)))]

    def queued(self, destination, message):
        return bool(self.connection.execute('SELECT 1 FROM cleanup WHERE destination_id=? AND message_id=?',
                                            (destination, message)).fetchone())

    def forget(self, destination, message):
        with self.connection:
            self.connection.execute('DELETE FROM cards WHERE destination_id=? AND message_id=?', (destination, message))
            self.connection.execute('DELETE FROM controls WHERE destination_id=? AND message_id=?', (destination, message))

    def compact(self, before):
        with self.connection:
            self.connection.execute('DELETE FROM request_cards WHERE created_at<?', (before,))
            self.connection.execute('DELETE FROM cards WHERE created_at<? AND NOT EXISTS '
                                    '(SELECT 1 FROM cleanup WHERE cleanup.destination_id=cards.destination_id AND cleanup.message_id=cards.message_id)', (before,))
            self.connection.execute('DELETE FROM links WHERE first_key NOT IN (SELECT group_key FROM cards) '
                                    'AND second_key NOT IN (SELECT group_key FROM cards)')

    def finish(self, destination, message):
        with self.connection:
            self.connection.execute('DELETE FROM cleanup WHERE destination_id=? AND message_id=?', (destination, message))
            self.forget(destination, message)

    def defer(self, destination, message, now):
        with self.connection:
            self.connection.execute('UPDATE cleanup SET attempts=attempts+1,retry_at=? WHERE destination_id=? AND message_id=?',
                                    (now + 300, destination, message))
