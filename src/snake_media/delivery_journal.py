"""Durable Discord delivery receipts; contains no credentials or media policy."""
import sqlite3


class DeliveryJournal:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        try:
            self.connection.execute('PRAGMA synchronous=FULL')
            self.connection.execute('CREATE TABLE IF NOT EXISTS receipts '
                                    '(notification_key TEXT PRIMARY KEY, message_id TEXT NOT NULL, '
                                    'acknowledged INTEGER NOT NULL DEFAULT 0)')
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

    def acknowledge(self, key):
        with self.connection:
            self.connection.execute('UPDATE receipts SET acknowledged=1 WHERE notification_key=?', (key,))
