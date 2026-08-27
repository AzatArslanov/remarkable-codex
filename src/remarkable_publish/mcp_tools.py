from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .artifacts import ArtifactStore
from .config import Settings
from .credentials import CredentialStore
from .docker_launcher import UPLOAD_TOOL_ANNOTATIONS, UPLOAD_TOOL_NAME
from .domain import LivePublishRequest, RenderedArtifact, publish_key
from .ports import LivePublisher
from .private_auth import PrivateAuthHttp, UserTokenProvider
from .simple_upload import SimpleUploadPublisher, UrllibSimpleUploadTransport
from .state import IdempotencyLedger, StateFailure


def tool_contracts() -> dict[str, dict[str, bool]]:
    return {UPLOAD_TOOL_NAME: dict(UPLOAD_TOOL_ANNOTATIONS)}


def _artifact_dict(artifact: RenderedArtifact) -> dict[str, Any]:
    return {
        "artifactId": artifact.artifact_id,
        "artifactPath": str(artifact.host_path),
        "artifactMimeType": artifact.mime_type,
        "artifactSize": artifact.size_bytes,
        "artifactSha256": artifact.sha256,
    }


def _failure(stage: str, code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "errorStage": stage, "errorCode": code, "message": message, **extra}


class RemarkableTools:
    def __init__(self, *, settings: Settings, artifacts: ArtifactStore, credentials: CredentialStore, ledger: IdempotencyLedger, live_publisher: LivePublisher | None = None) -> None:
        self.settings, self.artifacts, self.credentials = settings, artifacts, credentials
        self.ledger, self.live_publisher = ledger, live_publisher

    @classmethod
    def from_settings(cls, settings: Settings, *, artifacts: ArtifactStore | None = None) -> RemarkableTools:
        store = artifacts or ArtifactStore(
            settings.artifact_directory,
            host_root=settings.artifact_host_directory,
            import_roots=settings.import_roots,
        )
        credentials = CredentialStore(settings.state_directory)
        publisher = SimpleUploadPublisher(UserTokenProvider(credentials, PrivateAuthHttp()), UrllibSimpleUploadTransport())
        return cls(settings=settings, artifacts=store, credentials=credentials, ledger=IdempotencyLedger(settings.state_directory / "state.sqlite3"), live_publisher=publisher)

    def status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "backend": "simple-upload",
            "authenticated": self.credentials.is_authenticated,
            "markdownUpload": "available" if self.credentials.is_authenticated else "credential-missing",
            "artifactDirectory": str(self.settings.artifact_host_directory or self.settings.artifact_directory),
            "imageVersion": os.environ.get("REMARKABLE_IMAGE_VERSION", "host"),
            "message": "Markdown-to-PDF publishing is available when a device credential is configured",
        }

    def _render(self, markdown_text: str | None, file_path: str | None) -> RenderedArtifact:
        if (markdown_text is None) == (file_path is None):
            raise ValueError("provide exactly one of markdownText or filePath")
        return self.artifacts.render_markdown(markdown_text) if markdown_text is not None else self.artifacts.render_markdown_file(Path(file_path or ""))

    def upload_markdown(self, *, title: str, markdown_text: str | None = None, file_path: str | None = None) -> dict[str, Any]:
        try:
            requested_title = title.strip()
            if not requested_title:
                raise ValueError("title must not be empty")
            artifact = self._render(markdown_text, file_path)
        except (OSError, ValueError) as error:
            return _failure("input", "invalid-publish-request", str(error))
        key = publish_key(requested_title, artifact.sha256)
        common = {
            "backend": "simple-upload",
            "title": requested_title,
            "remoteTitle": requested_title,
            "idempotencyKey": key,
            "idempotencyReplay": False,
            **_artifact_dict(artifact),
        }
        if self.live_publisher is None:
            return _failure("configuration", "simple-upload-unavailable", "simple upload publisher is unavailable", **common)
        try:
            with self.ledger.publish_lock():
                recorded = self.ledger.lookup_success(key)
                if recorded is not None:
                    return {
                        "ok": True,
                        **common,
                        "idempotencyReplay": True,
                        "remoteDocumentId": recorded.remote_document_id,
                        "remoteHash": recorded.remote_hash,
                        "errorStage": None,
                        "errorCode": None,
                        "message": "Exact retry suppressed by the local successful-upload ledger",
                    }
                outcome = self.live_publisher.publish_artifact(LivePublishRequest(artifact, requested_title, key))
                live_common = {**common, "remoteTitle": outcome.remote_title}
                if not outcome.ok:
                    return _failure(
                        outcome.error_stage or "upload",
                        outcome.error_code or "simple-upload-response-unrecognized",
                        outcome.message
                        or "PDF upload was not verified; the rendered artifact was preserved",
                        **live_common,
                    )
                try:
                    self.ledger.record_success(key, requested_title, artifact.sha256, remote_document_id=outcome.remote_document_id, remote_hash=outcome.remote_hash)
                except StateFailure:
                    return _failure(
                        "state",
                        "idempotency-record-failed",
                        "PDF upload was confirmed, but local retry-suppression state could not be recorded; do not retry automatically",
                        **live_common,
                        remoteDocumentId=outcome.remote_document_id,
                        remoteHash=outcome.remote_hash,
                        deliveryStatus="confirmed",
                        retrySafe=False,
                    )
                return {
                    "ok": True,
                    **live_common,
                    "remoteDocumentId": outcome.remote_document_id,
                    "remoteHash": outcome.remote_hash,
                    "errorStage": None,
                    "errorCode": None,
                    "message": outcome.message,
                }
        except StateFailure:
            return _failure(
                "configuration",
                "idempotency-state-unavailable",
                "Local retry-suppression state is unavailable; no upload was attempted",
                **common,
            )
