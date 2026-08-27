import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from remarkable_publish.credentials import CredentialStore
from remarkable_publish.state import IdempotencyLedger


class CredentialAndStateTests(unittest.TestCase):
    def test_credential_and_ledger_permissions_are_restricted(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "state"
            credentials = CredentialStore(root)
            credentials.save("synthetic-token")
            ledger = IdempotencyLedger(root / "state.sqlite3")
            ledger.record_success("key", "Title", "a" * 64, remote_document_id="remote-id", remote_hash="b" * 64)

            self.assertEqual(stat.S_IMODE(credentials.directory.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(credentials.path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(ledger.path.stat().st_mode), 0o600)

            self.assertTrue(credentials.revoke_local())
            self.assertFalse(credentials.is_authenticated)


if __name__ == "__main__":
    unittest.main()
