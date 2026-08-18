from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path
import tomllib

from . import __version__
from .config import Settings, load_settings
from .credentials import CredentialStore
from .mcp_tools import RemarkableTools
from .private_auth import AuthenticationFailure, PrivateAuthHttp


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="remarkable-publish")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", type=Path, default=Path(".remarkable-publish.toml"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="validate Markdown publishing configuration")
    auth = commands.add_parser("auth", help="manage the local reMarkable credential")
    auth.add_argument("action", choices=("login", "status", "revoke"))
    upload = commands.add_parser("upload", help="render and upload one UTF-8 Markdown file")
    upload.add_argument("input", type=Path)
    upload.add_argument("--title", required=True)
    upload.add_argument("--live", action="store_true")
    upload.add_argument("--confirm-upload", action="store_true")
    return parser


def _print(value: dict) -> None:
    print(json.dumps(value, separators=(",", ":")))


def _error(stage: str, code: str, message: str) -> None:
    _print({"ok": False, "errorStage": stage, "errorCode": code, "message": message})


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings: Settings = load_settings(args.config)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        _error("configuration", "invalid-configuration", str(error))
        return 2
    if args.command == "doctor":
        _print(RemarkableTools.from_settings(settings).status())
        return 0
    if args.command == "auth":
        credentials = CredentialStore(settings.state_directory)
        if args.action == "status":
            _print({"ok": True, "authenticated": credentials.is_authenticated, "message": "credential is present" if credentials.is_authenticated else "credential is not configured"})
            return 0
        if args.action == "revoke":
            removed = credentials.revoke_local()
            _print({"ok": True, "revokedLocal": removed, "revokedRemote": False, "message": "local credential removed; remote revocation is unavailable"})
            return 0
        try:
            code = getpass.getpass("Pairing code: ")
            credentials.save(PrivateAuthHttp().register_device(code))
            _print({"ok": True, "authenticated": True, "message": "device credential stored securely"})
            return 0
        except (OSError, ValueError, AuthenticationFailure):
            _error("authentication", "device-pairing-failed", "device pairing failed")
            return 1
    result = RemarkableTools.from_settings(settings).upload_markdown(
        file_path=str(args.input), title=args.title,
        dry_run=not args.live,
        confirm_upload=args.confirm_upload,
    )
    _print(result)
    return 0 if result["ok"] else 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
