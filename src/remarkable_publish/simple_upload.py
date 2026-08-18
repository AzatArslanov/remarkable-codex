from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import re
from typing import Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .domain import LivePublishOutcome, LivePublishRequest
from .private_auth import AuthenticationFailure, NoRedirect


UPLOAD_URL = "https://internal.cloud.remarkable.com/doc/v2/files"
_HASH = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes


class HttpTransport(Protocol):
    def request(self, method: str, url: str, *, headers: Mapping[str, str], body: bytes) -> HttpResponse: ...


class TokenProvider(Protocol):
    def get(self) -> str: ...
    def invalidate(self) -> None: ...


class UrllibSimpleUploadTransport:
    def __init__(self, *, timeout: float = 60.0) -> None:
        self.timeout = timeout
        self.opener = build_opener(NoRedirect)

    def request(self, method: str, url: str, *, headers: Mapping[str, str], body: bytes) -> HttpResponse:
        if method != "POST" or url != UPLOAD_URL:
            raise ValueError("simple upload request target is not allowed")
        request = Request(url, data=body, method=method, headers=dict(headers))
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return HttpResponse(response.status, response.read())
        except HTTPError as error:
            return HttpResponse(error.code, b"")
        except (URLError, OSError) as error:
            raise OSError("simple upload request failed") from error


class SimpleUploadPublisher:
    name = "simple-upload"

    def __init__(self, tokens: TokenProvider, transport: HttpTransport) -> None:
        self.tokens = tokens
        self.transport = transport

    def _request(self, request: LivePublishRequest, token: str, pdf: bytes) -> HttpResponse:
        metadata = base64.b64encode(
            json.dumps({"file_name": request.title}, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        return self.transport.request(
            "POST",
            UPLOAD_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/pdf",
                "rm-meta": metadata,
                "rm-source": "RoR-Browser",
            },
            body=pdf,
        )

    def publish_artifact(self, request: LivePublishRequest) -> LivePublishOutcome:
        try:
            pdf = request.artifact.internal_path.read_bytes()
            response = self._request(request, self.tokens.get(), pdf)
            if response.status == 401:
                self.tokens.invalidate()
                response = self._request(request, self.tokens.get(), pdf)
                if response.status == 401:
                    self.tokens.invalidate()
                    return LivePublishOutcome(False, request.title, error_stage="authentication", error_code="private-authentication-failed", message="Authentication failed; the local artifact was preserved")
            if not 200 <= response.status < 300:
                return LivePublishOutcome(False, request.title, error_stage="upload", error_code="simple-upload-failed", message="PDF upload failed; the local artifact was preserved")
            loaded = json.loads(response.body.decode("utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError
            document_id, remote_hash = loaded.get("docID"), loaded.get("hash")
            if not isinstance(document_id, str) or not document_id or not isinstance(remote_hash, str) or not _HASH.fullmatch(remote_hash):
                raise ValueError
            return LivePublishOutcome(True, request.title, remote_document_id=document_id, remote_hash=remote_hash, message="PDF uploaded to the reMarkable library")
        except AuthenticationFailure as error:
            return LivePublishOutcome(False, request.title, error_stage="authentication", error_code=error.code, message="Authentication failed; the local artifact was preserved")
        except (OSError, UnicodeError):
            return LivePublishOutcome(False, request.title, error_stage="upload", error_code="simple-upload-failed", message="PDF upload failed; the local artifact was preserved")
        except (ValueError, json.JSONDecodeError):
            return LivePublishOutcome(False, request.title, error_stage="upload", error_code="simple-upload-response-unrecognized", message="Upload response was not recognized; the local artifact was preserved")
