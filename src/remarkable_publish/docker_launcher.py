from __future__ import annotations

import argparse
import errno
import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from tempfile import TemporaryDirectory, gettempdir
from threading import Lock, Thread
from time import monotonic
from uuid import uuid4

DEFAULT_IMAGE = "remarkable-codex-mcp:0.3.0"
DEFAULT_STATE_VOLUME = "remarkable-publish-state-v1"
MAX_MARKDOWN_BYTES = 10 * 1024 * 1024
CONTAINER_IMPORT_ROOT = Path("/imports/0")
MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_SERVER_NAME = "remarkable-publisher"
MCP_SERVER_VERSION = "1.27.2"
UPLOAD_TOOL_NAME = "upload_markdown"
PUBLICATION_RESPONSE_TIMEOUT_SECONDS = 60.0
CONTAINER_EXIT_TIMEOUT_SECONDS = 5.0
UPLOAD_TOOL_DESCRIPTION = (
    "Render Markdown as PDF and upload it to the reMarkable library. markdownText accepts "
    "inline content; filePath accepts any host-readable regular file and stages only that "
    "file into the isolated publisher container."
)
UPLOAD_TOOL_ANNOTATIONS = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
UPLOAD_TOOL = {
    "name": UPLOAD_TOOL_NAME,
    "description": UPLOAD_TOOL_DESCRIPTION,
    "inputSchema": {
        "properties": {
            "title": {"title": "Title", "type": "string"},
            "markdownText": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": None,
                "title": "Markdowntext",
            },
            "filePath": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": None,
                "title": "Filepath",
            },
        },
        "required": ["title"],
        "title": "upload_markdown_handlerArguments",
        "type": "object",
    },
    "annotations": UPLOAD_TOOL_ANNOTATIONS,
}


@dataclass(frozen=True, slots=True)
class DockerRuntime:
    image: str
    state_volume: str
    artifact_host_directory: Path
    uid: int
    gid: int


@dataclass(frozen=True, slots=True)
class BrokerDecision:
    forward: bytes | None = None
    response: bytes | None = None


class StagingFailure(ValueError):
    pass


def _json_line(payload: object) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def _tool_failure_response(
    request_id: object,
    *,
    stage: str,
    code: str,
    message: str,
    delivery_status: str | None = None,
    retry_safe: bool | None = None,
) -> bytes:
    failure = {
        "ok": False,
        "errorStage": stage,
        "errorCode": code,
        "message": message,
    }
    if delivery_status is not None:
        failure["deliveryStatus"] = delivery_status
    if retry_safe is not None:
        failure["retrySafe"] = retry_safe
    return _json_line(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(failure, separators=(",", ":")),
                    }
                ],
                "structuredContent": failure,
                "isError": False,
            },
        }
    )


class FilePathBroker:
    def __init__(self, staging_directory: Path) -> None:
        self.staging_directory = staging_directory
        self._pending: dict[str, Path] = {}
        self._lock = Lock()

    @staticmethod
    def _request_key(request_id: object) -> str:
        return json.dumps(request_id, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _failure_response(request_id: object, message: str) -> bytes:
        return _tool_failure_response(
            request_id,
            stage="input",
            code="invalid-publish-request",
            message=message,
        )

    def _stage(self, raw_path: str) -> Path:
        source = Path(raw_path).expanduser()
        descriptor: int | None = None
        try:
            flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(source, flags)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise StagingFailure("Markdown filePath must identify a regular file")
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = None
                encoded = handle.read(MAX_MARKDOWN_BYTES + 1)
        except OSError as error:
            if error.errno == errno.ELOOP:
                raise StagingFailure(
                    "Markdown filePath symlinks are not supported by the local staging broker"
                ) from error
            raise StagingFailure(
                "Markdown filePath is not readable by the local staging broker"
            ) from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
        if len(encoded) > MAX_MARKDOWN_BYTES:
            raise StagingFailure("Markdown source must be no larger than 10 MB")

        destination = self.staging_directory / f"{uuid4()}.md"
        output_descriptor: int | None = None
        try:
            output_descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(output_descriptor, "wb") as handle:
                output_descriptor = None
                handle.write(encoded)
        except OSError as error:
            destination.unlink(missing_ok=True)
            raise StagingFailure(
                "Markdown file could not be copied into private staging"
            ) from error
        finally:
            if output_descriptor is not None:
                os.close(output_descriptor)
        return destination

    def handle_client_line(self, line: bytes) -> BrokerDecision:
        try:
            request = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return BrokerDecision(forward=line)
        if not isinstance(request, dict) or request.get("method") != "tools/call":
            return BrokerDecision(forward=line)
        params = request.get("params")
        if not isinstance(params, dict) or params.get("name") != "upload_markdown":
            return BrokerDecision(forward=line)
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            return BrokerDecision(forward=line)
        raw_path = arguments.get("filePath")
        if isinstance(raw_path, str) and arguments.get("markdownText") is not None:
            return BrokerDecision(
                response=self._failure_response(
                    request.get("id"),
                    "provide exactly one of markdownText or filePath",
                )
            )
        if not isinstance(raw_path, str):
            return BrokerDecision(forward=line)
        request_id = request.get("id")
        try:
            staged = self._stage(raw_path)
        except (StagingFailure, ValueError) as error:
            return BrokerDecision(response=self._failure_response(request_id, str(error)))

        arguments["filePath"] = str(CONTAINER_IMPORT_ROOT / staged.name)
        forwarded = (json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            self._pending[self._request_key(request_id)] = staged
        return BrokerDecision(forward=forwarded)

    def handle_server_line(self, line: bytes) -> bytes:
        try:
            response = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return line
        if isinstance(response, dict) and "id" in response:
            with self._lock:
                staged = self._pending.pop(self._request_key(response["id"]), None)
            if staged is not None:
                staged.unlink(missing_ok=True)
        return line

    def cleanup(self) -> None:
        with self._lock:
            staged_files = tuple(self._pending.values())
            self._pending.clear()
        for staged in staged_files:
            staged.unlink(missing_ok=True)


PublicationRunner = Callable[[DockerRuntime, bytes], bytes]


class HostMcpServer:
    def __init__(
        self,
        runtime: DockerRuntime,
        *,
        publication_runner: PublicationRunner | None = None,
    ) -> None:
        self.runtime = runtime
        self.publication_runner = publication_runner or _run_publication_call

    @staticmethod
    def _result(request_id: object, result: object) -> bytes:
        return _json_line({"jsonrpc": "2.0", "id": request_id, "result": result})

    @staticmethod
    def _error(request_id: object, code: int, message: str) -> bytes:
        return _json_line(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": code, "message": message},
            }
        )

    def handle_client_line(self, line: bytes) -> bytes | None:
        try:
            request = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._error(None, -32700, "Parse error")
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            return self._error(None, -32600, "Invalid Request")

        method = request.get("method")
        request_id = request.get("id")
        if method == "initialize":
            return self._result(
                request_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": MCP_SERVER_NAME,
                        "version": MCP_SERVER_VERSION,
                    },
                },
            )
        if "id" not in request:
            return None
        if method == "ping":
            return self._result(request_id, {})
        if method == "tools/list":
            return self._result(request_id, {"tools": [UPLOAD_TOOL]})
        if method == "tools/call":
            params = request.get("params")
            if not isinstance(params, dict) or params.get("name") != UPLOAD_TOOL_NAME:
                return self._error(request_id, -32602, "Unknown tool")
            return self.publication_runner(self.runtime, line)
        return self._error(request_id, -32601, "Method not found")


def _mount(kind: str, source: str, destination: str, *, readonly: bool = False) -> str:
    value = f"type={kind},src={source},dst={destination}"
    return f"{value},readonly" if readonly else value


def docker_run_args(
    runtime: DockerRuntime,
    *,
    command: tuple[str, ...],
    staging_host_directory: Path | None = None,
    tty: bool = False,
) -> list[str]:
    artifacts = runtime.artifact_host_directory.resolve()
    args = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--init",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--memory=512m",
        "--cpus=1",
        "--pids-limit=128",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--user",
        f"{runtime.uid}:{runtime.gid}",
        "--mount",
        _mount("volume", runtime.state_volume, "/var/lib/remarkable-publish"),
        "--mount",
        _mount("bind", str(artifacts), "/artifacts"),
        "--env",
        "REMARKABLE_ARTIFACT_DIR=/artifacts",
        "--env",
        f"REMARKABLE_ARTIFACT_HOST_DIR={artifacts}",
        "--env",
        "REMARKABLE_STATE_DIR=/var/lib/remarkable-publish",
    ]
    if tty:
        args.insert(args.index("--init"), "-t")
    if staging_host_directory is not None:
        args.extend(
            [
                "--mount",
                _mount(
                    "bind",
                    str(staging_host_directory.resolve()),
                    str(CONTAINER_IMPORT_ROOT),
                    readonly=True,
                ),
                "--env",
                f"REMARKABLE_IMPORT_ROOTS={CONTAINER_IMPORT_ROOT}",
            ]
        )
    args.extend(
        [
            runtime.image,
            *command,
        ]
    )
    return args


def _runtime() -> DockerRuntime:
    default_artifact_root = Path(os.environ.get("TMPDIR") or gettempdir())
    artifact_directory = Path(
        os.environ.get(
            "REMARKABLE_ARTIFACT_HOST_DIR",
            str(default_artifact_root / "remarkable-publish" / "artifacts"),
        )
    ).expanduser()
    return DockerRuntime(
        image=os.environ.get("REMARKABLE_MCP_IMAGE", DEFAULT_IMAGE),
        state_volume=os.environ.get("REMARKABLE_STATE_VOLUME", DEFAULT_STATE_VOLUME),
        artifact_host_directory=artifact_directory,
        uid=os.getuid(),
        gid=os.getgid(),
    )


def _prepare_directories(runtime: DockerRuntime) -> None:
    runtime.artifact_host_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(runtime.artifact_host_directory, 0o700)


def _initialize_volume(runtime: DockerRuntime) -> None:
    subprocess.run(
        ["docker", "volume", "create", runtime.state_volume],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    owner = f"{runtime.uid}:{runtime.gid}"
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            "0:0",
            "--mount",
            _mount("volume", runtime.state_volume, "/state"),
            runtime.image,
            "sh",
            "-c",
            f"mkdir -p /state/credentials && chown -R {owner} /state && chmod 700 /state /state/credentials",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def _run_container(runtime: DockerRuntime, command: tuple[str, ...], *, tty: bool = False) -> int:
    _prepare_directories(runtime)
    _initialize_volume(runtime)
    completed = subprocess.run(docker_run_args(runtime, command=command, tty=tty), check=False)
    return completed.returncode


def _matching_response(output: bytes, request_id: object) -> bytes | None:
    for line in output.splitlines(keepends=True):
        try:
            response = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(response, dict) and response.get("id") == request_id:
            return line if line.endswith(b"\n") else line + b"\n"
    return None


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.stdin is not None and not process.stdin.closed:
        with suppress(OSError):
            process.stdin.close()
    if process.poll() is not None:
        return
    try:
        process.wait(timeout=CONTAINER_EXIT_TIMEOUT_SECONDS)
        return
    except subprocess.TimeoutExpired:
        process.terminate()
    try:
        process.wait(timeout=CONTAINER_EXIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _exchange_with_container(
    args: list[str],
    payload: bytes,
    request_id: object,
    *,
    timeout: float = PUBLICATION_RESPONSE_TIMEOUT_SECONDS,
) -> bytes | None:
    process = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    lines: Queue[bytes | None] = Queue()

    def read_stdout() -> None:
        try:
            if process.stdout is not None:
                for line in process.stdout:
                    lines.put(line)
        finally:
            lines.put(None)

    reader = Thread(target=read_stdout, daemon=True)
    reader.start()
    try:
        if process.stdin is None:
            return None
        try:
            process.stdin.write(payload)
            process.stdin.flush()
        except OSError:
            return None

        deadline = monotonic() + timeout
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                return None
            try:
                line = lines.get(timeout=remaining)
            except Empty:
                return None
            if line is None:
                return None
            response = _matching_response(line, request_id)
            if response is not None:
                return response
    finally:
        _stop_process(process)
        reader.join(timeout=CONTAINER_EXIT_TIMEOUT_SECONDS)
        if process.stdout is not None and not process.stdout.closed:
            process.stdout.close()


def _run_publication_call(runtime: DockerRuntime, request_line: bytes) -> bytes:
    try:
        request = json.loads(request_line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HostMcpServer._error(None, -32700, "Parse error")
    request_id = request.get("id") if isinstance(request, dict) else None
    with TemporaryDirectory(prefix="remarkable-import-") as directory:
        staging = Path(directory)
        os.chmod(staging, 0o700)
        broker = FilePathBroker(staging)
        decision = broker.handle_client_line(request_line)
        if decision.response is not None:
            return decision.response
        if decision.forward is None:
            return _tool_failure_response(
                request_id,
                stage="input",
                code="invalid-publish-request",
                message="Invalid upload_markdown request",
            )

        internal_id = f"host-initialize-{uuid4()}"
        initialization = _json_line(
            {
                "jsonrpc": "2.0",
                "id": internal_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "remarkable-publish-host-broker",
                        "version": DEFAULT_IMAGE.rsplit(":", 1)[-1],
                    },
                },
            }
        )
        initialized = _json_line(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        try:
            _prepare_directories(runtime)
            _initialize_volume(runtime)
            response = _exchange_with_container(
                docker_run_args(
                    runtime,
                    command=("remarkable-publish-mcp",),
                    staging_host_directory=staging,
                ),
                initialization + initialized + decision.forward,
                request_id,
            )
            if response is not None:
                return broker.handle_server_line(response)
            return _tool_failure_response(
                request_id,
                stage="configuration",
                code="docker-protocol-failed",
                message=(
                    "Docker publisher exited without a matching response; "
                    "no delivery was verified"
                ),
                delivery_status="unknown",
                retry_safe=False,
            )
        except (OSError, subprocess.SubprocessError):
            return _tool_failure_response(
                request_id,
                stage="configuration",
                code="docker-launch-failed",
                message="Docker publisher could not be started; no upload was attempted",
            )
        finally:
            broker.cleanup()


def _serve_container(runtime: DockerRuntime) -> int:
    server = HostMcpServer(runtime)
    for line in sys.stdin.buffer:
        response = server.handle_client_line(line)
        if response is not None:
            sys.stdout.buffer.write(response)
            sys.stdout.buffer.flush()
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="remarkable-publish-mcp-docker")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve")
    build = commands.add_parser("build")
    build.add_argument("--context", type=Path, default=Path.cwd())
    auth = commands.add_parser("auth")
    auth.add_argument("action", choices=("login", "status", "revoke"))
    commands.add_parser("status")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    runtime = _runtime()
    command = args.command or "serve"
    try:
        if command == "build":
            completed = subprocess.run(
                [
                    "docker",
                    "build",
                    "--pull",
                    "--tag",
                    runtime.image,
                    str(args.context.resolve()),
                ],
                check=False,
            )
            raise SystemExit(completed.returncode)
        if command == "serve":
            raise SystemExit(_serve_container(runtime))
        if command == "status":
            raise SystemExit(_run_container(runtime, ("remarkable-publish", "doctor")))
        action = args.action
        raise SystemExit(
            _run_container(
                runtime,
                ("remarkable-publish", "auth", action),
                tty=action == "login",
            )
        )
    except (OSError, subprocess.SubprocessError) as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errorStage": "configuration",
                    "errorCode": "docker-launch-failed",
                    "message": str(error),
                },
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
