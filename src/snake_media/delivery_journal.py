"""Durable Discord delivery receipts; contains no credentials or media policy."""
import sqlite3
import math


class DeliveryJournal:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        try:
            self.connection.execute('PRAGMA synchronous=FULL')
            self.connection.execute('CREATE TABLE IF NOT EXISTS receipts '
                                    '(notification_key TEXT PRIMARY KEY, message_id TEXT NOT NULL, '
                                    'acknowledged INTEGER NOT NULL DEFAULT 0)')
            self.connection.execute('CREATE TABLE IF NOT EXISTS retries '
                                    '(notification_key TEXT PRIMARY KEY, attempts INTEGER NOT NULL, '
                                    'retry_at REAL NOT NULL, updated_at REAL NOT NULL)')
            self.connection.commit()
        except Exception:
            self.connection.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    def get(self, key):
        row = self.connection.execute('SELECT message_id FROM receipts WHERE notification_key=?',
                                      (key,)).fetchone()
        return row[0] if row else None

    def pending(self):
        return dict(self.connection.execute('SELECT notification_key,message_id FROM receipts '
                                            'WHERE acknowledged=0'))

    def record(self, key, message_id):
        with self.connection:
            old = self.get(key)
            if old is not None and old != message_id:
                raise ValueError('delivery_receipt_conflict')
            self.connection.execute('INSERT OR IGNORE INTO receipts '
                                    '(notification_key,message_id) VALUES (?,?)', (key, message_id))
            self.connection.execute('DELETE FROM retries WHERE notification_key=?', (key,))

    @staticmethod
    def _valid_retry(key, attempts, due):
        return (isinstance(key, str) and 1 <= len(key) <= 300 and
                type(attempts) is int and 1 <= attempts <= 5 and
                type(due) in (int, float) and math.isfinite(due) and due >= 0)

    def retries(self):
        rows = self.connection.execute('SELECT notification_key,attempts,retry_at FROM retries '
                                       'ORDER BY updated_at,rowid LIMIT 1001').fetchall()
        if len(rows) > 1000 or any(not self._valid_retry(*row) for row in rows):
            raise ValueError('invalid_notification_retry_state')
        return {key: (attempts, due) for key, attempts, due in rows}

    def defer(self, key, attempts, due, updated):
        if (not self._valid_retry(key, attempts, due) or type(updated) not in (int, float)
                or not math.isfinite(updated) or updated < 0):
            raise ValueError('invalid_notification_retry')
        with self.connection:
            self.connection.execute('INSERT INTO retries (notification_key,attempts,retry_at,updated_at) '
                                    'VALUES (?,?,?,?) ON CONFLICT(notification_key) DO UPDATE SET '
                                    'attempts=excluded.attempts,retry_at=excluded.retry_at,updated_at=excluded.updated_at',
                                    (key, attempts, due, updated))
            self.connection.execute('DELETE FROM retries WHERE notification_key NOT IN '
                                    '(SELECT notification_key FROM retries ORDER BY updated_at DESC,rowid DESC LIMIT 1000)')

    def acknowledge(self, key):
        with self.connection:
            self.connection.execute('UPDATE receipts SET acknowledged=1 WHERE notification_key=?', (key,))
