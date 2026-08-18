from __future__ import annotations

import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Lock, Thread
import time
import unittest

from remarkable_publish.artifacts import ArtifactStore
from remarkable_publish.config import Settings
from remarkable_publish.credentials import CredentialStore
from remarkable_publish.domain import LivePublishOutcome
from remarkable_publish.mcp_server import upload_markdown_handler
from remarkable_publish.mcp_tools import RemarkableTools, tool_contracts
from remarkable_publish.state import IdempotencyLedger, StateFailure


class FakePublisher:
    name = "simple-upload"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.requests = []

    def publish_artifact(self, request):
        self.requests.append(request)
        if self.fail:
            return LivePublishOutcome(False, request.title, error_stage="upload", error_code="simple-upload-failed", message="PDF upload failed; the local artifact was preserved")
        return LivePublishOutcome(True, request.title, remote_document_id="remote-id", remote_hash="b" * 64, message="PDF uploaded to the reMarkable library")


class SlowPublisher(FakePublisher):
    def __init__(self) -> None:
        super().__init__()
        self._lock = Lock()

    def publish_artifact(self, request):
        with self._lock:
            self.requests.append(request)
        time.sleep(0.15)
        return LivePublishOutcome(
            True,
            request.title,
            remote_document_id="remote-id",
            remote_hash="b" * 64,
            message="PDF uploaded to the reMarkable library",
        )


class FailingRecordLedger(IdempotencyLedger):
    def record_success(self, *args, **kwargs) -> None:
        raise StateFailure("successful upload state could not be recorded")


class McpContractTests(unittest.TestCase):
    def _tools(self, root: Path, *, settings: Settings | None = None, publisher=None):
        state = root / "state"
        return RemarkableTools(
            settings=settings or Settings(artifact_directory=root / "artifacts", state_directory=state, import_roots=(root,)),
            artifacts=ArtifactStore(root / "artifacts", import_roots=(root,)),
            credentials=CredentialStore(state), ledger=IdempotencyLedger(state / "state.sqlite3"), live_publisher=publisher,
        )

    def test_schema_exposes_only_simple_upload_inputs(self) -> None:
        parameters = inspect.signature(upload_markdown_handler).parameters
        self.assertEqual(set(parameters), {"title", "markdownText", "filePath", "dryRun", "confirmUpload"})
        self.assertEqual(set(tool_contracts()), {"upload_markdown"})

    def test_text_defaults_to_rendered_pdf_dry_run_without_network(self) -> None:
        with TemporaryDirectory() as directory:
            publisher = FakePublisher()
            source = "# Brief\n\nHello **paper**. PRIVATE-BODY"
            result = self._tools(Path(directory), publisher=publisher).upload_markdown(markdown_text=source, title="Brief")
            self.assertTrue(result["ok"])
            self.assertEqual(result["backend"], "dry-run")
            self.assertEqual(result["artifactMimeType"], "application/pdf")
            self.assertTrue(Path(result["artifactPath"]).is_file())
            self.assertEqual(publisher.requests, [])
            self.assertNotIn("PRIVATE-BODY", str(result))

    def test_file_is_always_read_as_utf8_markdown_regardless_of_suffix(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.txt"
            source.write_text("# Notes\n\n- one\n- two", encoding="utf-8")
            tools = self._tools(root)
            from_file = tools.upload_markdown(file_path=str(source), title="Notes")
            from_text = tools.upload_markdown(markdown_text=source.read_text(), title="Notes")
            self.assertEqual(from_file["artifactSha256"], from_text["artifactSha256"])
            self.assertEqual(from_file["idempotencyKey"], from_text["idempotencyKey"])

    def test_exactly_one_markdown_source_is_required(self) -> None:
        with TemporaryDirectory() as directory:
            tools = self._tools(Path(directory))
            self.assertEqual(tools.upload_markdown(title="Brief")["errorCode"], "invalid-publish-request")
            self.assertEqual(tools.upload_markdown(markdown_text="hello", file_path="hello.md", title="Brief")["errorCode"], "invalid-publish-request")

    def test_live_upload_requires_confirmation_and_simple_upload_opt_in(self) -> None:
        with TemporaryDirectory() as directory:
            tools = self._tools(Path(directory))
            self.assertEqual(tools.upload_markdown(markdown_text="hello", title="Brief", dry_run=False)["errorCode"], "confirmation-required")
            result = tools.upload_markdown(markdown_text="hello", title="Brief", dry_run=False, confirm_upload=True)
            self.assertEqual(result["errorCode"], "simple-upload-disabled")

    def test_successful_exact_retry_is_suppressed_locally(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            publisher = FakePublisher()
            settings = Settings(backend="simple-upload", experimental_simple_upload=True, artifact_directory=root / "artifacts", state_directory=root / "state", import_roots=(root,))
            tools = self._tools(root, settings=settings, publisher=publisher)
            first = tools.upload_markdown(markdown_text="# Brief", title="Brief", dry_run=False, confirm_upload=True)
            second = tools.upload_markdown(markdown_text="# Brief", title="Brief", dry_run=False, confirm_upload=True)
            self.assertTrue(first["ok"] and second["ok"])
            self.assertEqual(len(publisher.requests), 1)
            self.assertTrue(second["idempotencyReplay"])
            self.assertEqual(first.get("remoteDocumentId"), second.get("remoteDocumentId"))

    def test_concurrent_exact_retries_are_serialized(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            publisher = SlowPublisher()
            settings = Settings(backend="simple-upload", experimental_simple_upload=True, artifact_directory=root / "artifacts", state_directory=root / "state")
            tools = self._tools(root, settings=settings, publisher=publisher)
            tools.upload_markdown(markdown_text="# Warmup", title="Warmup")
            start = Barrier(3)
            results = []

            def publish() -> None:
                start.wait()
                results.append(tools.upload_markdown(markdown_text="# Same", title="Same", dry_run=False, confirm_upload=True))

            threads = [Thread(target=publish), Thread(target=publish)]
            for thread in threads:
                thread.start()
            start.wait()
            for thread in threads:
                thread.join(timeout=3)

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(len(publisher.requests), 1)
            self.assertEqual(sorted(result["idempotencyReplay"] for result in results), [False, True])

    def test_corrupt_ledger_returns_classified_failure_before_upload(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            state.mkdir()
            (state / "state.sqlite3").write_bytes(b"not sqlite")
            publisher = FakePublisher()
            settings = Settings(backend="simple-upload", experimental_simple_upload=True, artifact_directory=root / "artifacts", state_directory=state)
            result = self._tools(root, settings=settings, publisher=publisher).upload_markdown(markdown_text="# Brief", title="Brief", dry_run=False, confirm_upload=True)

            self.assertFalse(result["ok"])
            self.assertEqual(result["errorStage"], "configuration")
            self.assertEqual(result["errorCode"], "idempotency-state-unavailable")
            self.assertTrue(Path(result["artifactPath"]).is_file())
            self.assertEqual(publisher.requests, [])

    def test_post_upload_ledger_failure_reports_confirmed_non_retryable_delivery(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            publisher = FakePublisher()
            settings = Settings(backend="simple-upload", experimental_simple_upload=True, artifact_directory=root / "artifacts", state_directory=state)
            tools = RemarkableTools(
                settings=settings,
                artifacts=ArtifactStore(root / "artifacts"),
                credentials=CredentialStore(state),
                ledger=FailingRecordLedger(state / "state.sqlite3"),
                live_publisher=publisher,
            )
            result = tools.upload_markdown(markdown_text="# Brief", title="Brief", dry_run=False, confirm_upload=True)

            self.assertFalse(result["ok"])
            self.assertEqual(result["errorStage"], "state")
            self.assertEqual(result["errorCode"], "idempotency-record-failed")
            self.assertEqual(result["deliveryStatus"], "confirmed")
            self.assertFalse(result["retrySafe"])
            self.assertEqual(result["remoteDocumentId"], "remote-id")
            self.assertTrue(Path(result["artifactPath"]).is_file())

    def test_transport_failure_preserves_pdf_and_sanitizes_result(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            publisher = FakePublisher(fail=True)
            settings = Settings(backend="simple-upload", experimental_simple_upload=True, artifact_directory=root / "artifacts", state_directory=root / "state", import_roots=(root,))
            result = self._tools(root, settings=settings, publisher=publisher).upload_markdown(markdown_text="# Brief\nPRIVATE-BODY", title="Brief", dry_run=False, confirm_upload=True)
            self.assertFalse(result["ok"])
            self.assertEqual(result["errorCode"], "simple-upload-failed")
            self.assertTrue(Path(result["artifactPath"]).is_file())
            self.assertNotIn("PRIVATE-BODY", str(result))
            self.assertNotIn("secret", str(result).lower())


if __name__ == "__main__":
    unittest.main()
