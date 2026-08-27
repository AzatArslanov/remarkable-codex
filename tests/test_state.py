import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from remarkable_publish.state import IdempotencyLedger


class StateTests(unittest.TestCase):
    def test_records_only_successful_uploads_for_local_suppression(self) -> None:
        with TemporaryDirectory() as directory:
            ledger = IdempotencyLedger(Path(directory) / "state.sqlite3")
            self.assertIsNone(ledger.lookup_success("key"))
            ledger.record_success("key", "Title", "a" * 64, remote_document_id="remote-id", remote_hash="b" * 64)
            recorded = ledger.lookup_success("key")
            self.assertIsNotNone(recorded)
            self.assertEqual(recorded.remote_document_id, "remote-id")
            self.assertEqual(recorded.remote_hash, "b" * 64)

if __name__ == "__main__":
    unittest.main()
