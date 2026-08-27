from __future__ import annotations

import fcntl
import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SuccessfulUpload:
    idempotency_key: str
    title: str
    artifact_sha256: str
    remote_document_id: str | None
    remote_hash: str | None


class StateFailure(RuntimeError):
    """Sanitized failure raised when local idempotency state is unavailable."""


class IdempotencyLedger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection: sqlite3.Connection | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            connection = sqlite3.connect(self.path)
            os.chmod(self.path, 0o600)
            connection.execute(
                """CREATE TABLE IF NOT EXISTS successful_simple_uploads (
                    idempotency_key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    remote_document_id TEXT,
                    remote_hash TEXT)"""
            )
            return connection
        except (OSError, sqlite3.Error) as error:
            if connection is not None:
                connection.close()
            raise StateFailure("local idempotency state is unavailable") from error

    @contextmanager
    def publish_lock(self) -> Iterator[None]:
        """Serialize the lookup/upload/record sequence across local processes."""
        descriptor: int | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            lock_path = self.path.parent / ".publish.lock"
            descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            os.chmod(lock_path, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        except OSError as error:
            if descriptor is not None:
                os.close(descriptor)
            raise StateFailure("local idempotency state is unavailable") from error
        try:
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def lookup_success(self, idempotency_key: str) -> SuccessfulUpload | None:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT idempotency_key, title, artifact_sha256, remote_document_id, remote_hash FROM successful_simple_uploads WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
        except sqlite3.Error as error:
            raise StateFailure("local idempotency state is unavailable") from error
        return SuccessfulUpload(*row) if row else None

    def record_success(self, idempotency_key: str, title: str, artifact_sha256: str, *, remote_document_id: str | None, remote_hash: str | None) -> None:
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    "INSERT OR IGNORE INTO successful_simple_uploads (idempotency_key, title, artifact_sha256, remote_document_id, remote_hash) VALUES (?, ?, ?, ?, ?)",
                    (idempotency_key, title, artifact_sha256, remote_document_id, remote_hash),
                )
                connection.commit()
        except sqlite3.Error as error:
            raise StateFailure("successful upload state could not be recorded") from error
