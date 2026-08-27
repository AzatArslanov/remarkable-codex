from __future__ import annotations

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from .credentials import CredentialStore

AUTH_HOST = "https://webapp-prod.cloud.remarkable.engineering"


class AuthenticationFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class TokenExchange(Protocol):
    def exchange(self, device_token: str) -> str: ...


class PrivateAuthHttp:
    def __init__(self, *, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.opener = build_opener(NoRedirect)

    def _token_request(self, path: str, *, authorization: str, payload: bytes | None = None) -> str:
        request = Request(
            f"{AUTH_HOST}{path}", data=payload, method="POST",
            headers={"Authorization": authorization, "Content-Type": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                token = response.read().decode("utf-8").strip()
        except (HTTPError, URLError, OSError, UnicodeError) as error:
            raise AuthenticationFailure("private-authentication-failed", "private authentication request failed") from error
        if not token:
            raise AuthenticationFailure("private-authentication-failed", "private authentication returned no credential")
        return token

    def register_device(self, code: str) -> str:
        value = code.strip()
        if len(value) != 8:
            raise ValueError("pairing code must contain exactly 8 characters")
        payload = json.dumps(
            {"code": value, "deviceDesc": "desktop-linux", "deviceID": str(uuid4())},
            separators=(",", ":"),
        ).encode("utf-8")
        return self._token_request("/token/json/2/device/new", authorization="Bearer", payload=payload)

    def exchange(self, device_token: str) -> str:
        return self._token_request("/token/json/2/user/new", authorization=f"Bearer {device_token}")


class UserTokenProvider:
    def __init__(self, credentials: CredentialStore, exchange: TokenExchange) -> None:
        self.credentials = credentials
        self.exchange = exchange
        self._token: str | None = None

    def get(self) -> str:
        if self._token is None:
            try:
                self._token = self.exchange.exchange(self.credentials.load())
            except AuthenticationFailure:
                raise
            except (OSError, ValueError) as error:
                raise AuthenticationFailure("credential-missing", "stored device credential is missing") from error
        return self._token

    def invalidate(self) -> None:
        self._token = None
