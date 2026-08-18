from __future__ import annotations

import os
from pathlib import Path


class CredentialStore:
    """Restricted token storage for the dedicated Docker state volume."""

    def __init__(self, state_directory: Path) -> None:
        self.directory = state_directory / "credentials"
        self.path = self.directory / "device-token"

    def _ensure_directory(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)

    @property
    def is_authenticated(self) -> bool:
        try:
            return self.path.is_file() and bool(self.path.read_text(encoding="utf-8").strip())
        except OSError:
            return False

    def save(self, token: str) -> None:
        value = token.strip()
        if not value:
            raise ValueError("device token must not be empty")
        self._ensure_directory()
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(descriptor, value.encode("utf-8"))
        finally:
            os.close(descriptor)
        os.chmod(self.path, 0o600)

    def load(self) -> str:
        if not self.is_authenticated:
            raise ValueError("reMarkable authentication is not configured")
        return self.path.read_text(encoding="utf-8").strip()

    def revoke_local(self) -> bool:
        existed = self.path.exists()
        self.path.unlink(missing_ok=True)
        return existed
