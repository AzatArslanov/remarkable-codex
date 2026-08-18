from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


def publish_key(title: str, artifact_sha256: str) -> str:
    payload = "\0".join((title.strip(), artifact_sha256)).encode("utf-8")
    return sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class RenderedArtifact:
    artifact_id: str
    internal_path: Path
    host_path: Path
    size_bytes: int
    sha256: str
    mime_type: str


@dataclass(frozen=True, slots=True)
class LivePublishRequest:
    artifact: RenderedArtifact
    title: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class LivePublishOutcome:
    ok: bool
    remote_title: str
    remote_document_id: str | None = None
    remote_hash: str | None = None
    error_stage: str | None = None
    error_code: str | None = None
    message: str | None = None
