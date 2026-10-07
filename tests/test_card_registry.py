from pathlib import Path
import tempfile
import unittest
from snake_media.card_registry import CardRegistry


class CardRegistryTests(unittest.TestCase):
    def test_related_cards_survive_restart_and_only_owned_destination_is_consumed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cards.sqlite3'
            with CardRegistry(path) as cards:
                cards.remember('notice:12', '333', '100', '111')
                cards.remember('notice:12', '333', '101', '111')
                cards.remember('pending:13', '333', '102', '111')
                cards.link('notice:12', 'pending:13', '111', '333')
                self.assertEqual(cards.consume('pending:13', '222', '333', '102'), 0)
                self.assertEqual(cards.consume('pending:13', '111', '444', '102'), 0)
                self.assertEqual(cards.consume('pending:13', '111', '333', '102'), 2)
            with CardRegistry(path) as cards:
                self.assertEqual({j['message_id'] for j in cards.pending(now=0)}, {'100', '101'})
                cards.finish('333', '100')
                cards.defer('333', '101', now=100)
                self.assertEqual(cards.pending(now=100), [])
                self.assertEqual([j['message_id'] for j in cards.pending(now=1000)], ['101'])
                self.assertEqual(cards.consume('pending:13', '111', '333', '102'), 0)

    def test_message_binding_conflicts_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with CardRegistry(Path(folder) / 'cards.sqlite3') as cards:
                cards.remember('pending:1', '333', '100', '111')
                with self.assertRaises(ValueError):
                    cards.remember('pending:1', '333', '100', '222')
