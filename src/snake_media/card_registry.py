"""Durable transport-only references to related public Discord cards."""
import re
import sqlite3
import time


class CardRegistry:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('CREATE TABLE IF NOT EXISTS cards (group_key TEXT, destination_id TEXT, '
                                'message_id TEXT, owner_id TEXT, PRIMARY KEY(group_key,destination_id,message_id))')
        self.connection.execute('CREATE TABLE IF NOT EXISTS links (first_key TEXT, second_key TEXT, '
                                'owner_id TEXT, destination_id TEXT, PRIMARY KEY(first_key,second_key,owner_id,destination_id))')
        self.connection.execute('CREATE TABLE IF NOT EXISTS cleanup (destination_id TEXT, message_id TEXT, '
                                'retry_at REAL NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, '
                                'PRIMARY KEY(destination_id,message_id))')
        if 'created_at' not in {r[1] for r in self.connection.execute('PRAGMA table_info(cards)')}:
            self.connection.execute('ALTER TABLE cards ADD COLUMN created_at REAL')
        self.connection.execute('UPDATE cards SET created_at=? WHERE created_at IS NULL', (time.time(),))
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
        return [dict(r) for r in self.connection.execute('SELECT * FROM cleanup WHERE retry_at<=? AND attempts<12 ORDER BY retry_at LIMIT ?', (now, min(limit, 5)))]

    def forget(self, destination, message):
        with self.connection:
            self.connection.execute('DELETE FROM cards WHERE destination_id=? AND message_id=?', (destination, message))

    def compact(self, before):
        with self.connection:
            self.connection.execute('DELETE FROM cards WHERE created_at<? AND NOT EXISTS '
                                    '(SELECT 1 FROM cleanup WHERE cleanup.destination_id=cards.destination_id AND cleanup.message_id=cards.message_id)', (before,))
            self.connection.execute('DELETE FROM links WHERE first_key NOT IN (SELECT group_key FROM cards) '
                                    'AND second_key NOT IN (SELECT group_key FROM cards)')

    def finish(self, destination, message):
        with self.connection:
            self.connection.execute('DELETE FROM cleanup WHERE destination_id=? AND message_id=?', (destination, message))

    def defer(self, destination, message, now):
        with self.connection:
            self.connection.execute('UPDATE cleanup SET attempts=attempts+1,retry_at=? WHERE destination_id=? AND message_id=?',
                                    (now + 300, destination, message))
