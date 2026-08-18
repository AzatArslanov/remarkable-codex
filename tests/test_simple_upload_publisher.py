from __future__ import annotations

import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from remarkable_publish.domain import LivePublishRequest, RenderedArtifact
from remarkable_publish.simple_upload import HttpResponse, SimpleUploadPublisher


class FakeTokens:
    def get(self) -> str:
        return "secret-user-token"


class RecordingTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.requests = []

    def request(self, method, url, *, headers, body):
        self.requests.append((method, url, headers, body))
        return self.response


class SimpleUploadPublisherTests(unittest.TestCase):
    def _request(self, root: Path, *, title: str = "Brief") -> LivePublishRequest:
        path = root / "brief.pdf"
        path.write_bytes(b"%PDF-1.4\nprivate document body\n%%EOF\n")
        artifact = RenderedArtifact("pdf-x", path, path, path.stat().st_size, "a" * 64, "application/pdf")
        return LivePublishRequest(artifact, title, "key")

    def test_live_publish_invokes_one_simple_upload_operation(self) -> None:
        with TemporaryDirectory() as directory:
            transport = RecordingTransport(HttpResponse(201, b'{"docID":"remote-id","hash":"' + b"b" * 64 + b'"}'))
            outcome = SimpleUploadPublisher(FakeTokens(), transport).publish_artifact(self._request(Path(directory)))

        self.assertTrue(outcome.ok)
        self.assertEqual(len(transport.requests), 1)
        method, url, headers, body = transport.requests[0]
        self.assertEqual((method, url), ("POST", "https://internal.cloud.remarkable.com/doc/v2/files"))
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertEqual(headers["rm-source"], "RoR-Browser")
        self.assertEqual(json.loads(base64.b64decode(headers["rm-meta"])), {"file_name": "Brief"})
        self.assertEqual(body, b"%PDF-1.4\nprivate document body\n%%EOF\n")
        self.assertNotIn("secret-user-token", str(outcome))

    def test_unrecognized_response_fails_without_leaking_response_or_content(self) -> None:
        with TemporaryDirectory() as directory:
            transport = RecordingTransport(HttpResponse(200, b'{"token":"secret-user-token","body":"private document body"}'))
            outcome = SimpleUploadPublisher(FakeTokens(), transport).publish_artifact(self._request(Path(directory)))

        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.error_code, "simple-upload-response-unrecognized")
        self.assertNotIn("secret-user-token", str(outcome))
        self.assertNotIn("private document body", str(outcome))


if __name__ == "__main__":
    unittest.main()
