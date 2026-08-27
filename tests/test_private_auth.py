import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from remarkable_publish.credentials import CredentialStore
from remarkable_publish.domain import LivePublishRequest, RenderedArtifact
from remarkable_publish.private_auth import AuthenticationFailure, UserTokenProvider
from remarkable_publish.simple_upload import HttpResponse, SimpleUploadPublisher


class FakeExchange:
    def __init__(self) -> None:
        self.calls = []

    def exchange(self, device_token: str) -> str:
        self.calls.append(device_token)
        return f"user-{len(self.calls)}"


class RefreshTransport:
    def __init__(self) -> None:
        self.authorization = []

    def request(self, method, url, *, headers, body):
        self.authorization.append(headers["Authorization"])
        if len(self.authorization) == 1:
            return HttpResponse(401, b"")
        return HttpResponse(200, b'{"docID":"remote-id","hash":"' + b"0" * 64 + b'"}')


class AlwaysUnauthorizedTransport:
    def request(self, method, url, *, headers, body):
        return HttpResponse(401, b"")


class PrivateAuthTests(unittest.TestCase):
    def test_user_token_is_cached_in_memory_and_refreshed_once_on_401(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            credentials = CredentialStore(root)
            credentials.save("device-secret")
            exchange = FakeExchange()
            tokens = UserTokenProvider(credentials, exchange)
            transport = RefreshTransport()
            pdf = root / "test.pdf"
            pdf.write_bytes(b"pdf")
            artifact = RenderedArtifact("pdf-x", pdf, pdf, 3, "a" * 64, "application/pdf")
            outcome = SimpleUploadPublisher(tokens, transport).publish_artifact(LivePublishRequest(artifact, "Title", "key"))
            self.assertTrue(outcome.ok)
            self.assertEqual(exchange.calls, ["device-secret", "device-secret"])
            self.assertEqual(transport.authorization, ["Bearer user-1", "Bearer user-2"])

    def test_missing_credential_is_classified_without_secret_text(self) -> None:
        with TemporaryDirectory() as directory:
            tokens = UserTokenProvider(CredentialStore(Path(directory)), FakeExchange())
            with self.assertRaises(AuthenticationFailure) as captured:
                tokens.get()
            self.assertEqual(captured.exception.code, "credential-missing")
            self.assertNotIn("token", str(captured.exception).lower())

    def test_second_401_is_classified_as_authentication_failure(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            credentials = CredentialStore(root)
            credentials.save("device-secret")
            pdf = root / "document.pdf"
            pdf.write_bytes(b"pdf")
            exchange = FakeExchange()
            outcome = SimpleUploadPublisher(
                UserTokenProvider(credentials, exchange),
                AlwaysUnauthorizedTransport(),
            ).publish_artifact(
                LivePublishRequest(
                    RenderedArtifact(
                        "pdf-x",
                        pdf,
                        pdf,
                        3,
                        "a" * 64,
                        "application/pdf",
                    ),
                    "Title",
                    "key",
                )
            )
            self.assertFalse(outcome.ok)
            self.assertEqual(outcome.error_stage, "authentication")
            self.assertEqual(outcome.error_code, "private-authentication-failed")
            self.assertEqual(exchange.calls, ["device-secret", "device-secret"])


if __name__ == "__main__":
    unittest.main()
