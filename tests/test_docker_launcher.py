import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from remarkable_publish.docker_launcher import (
    MAX_MARKDOWN_BYTES,
    UPLOAD_TOOL,
    DockerRuntime,
    FilePathBroker,
    HostMcpServer,
    _run_publication_call,
    _runtime,
    docker_run_args,
)
from remarkable_publish.mcp_tools import tool_contracts


class DockerLauncherTests(unittest.TestCase):
    def test_mcp_discovery_does_not_start_the_publication_runner(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = DockerRuntime(
                image="remarkable-codex-mcp:0.3.0",
                state_volume="remarkable-publish-state-v1",
                artifact_host_directory=Path(directory) / "artifacts",
                uid=501,
                gid=20,
            )
            publication_calls: list[bytes] = []

            def publish(_runtime: DockerRuntime, request: bytes) -> bytes:
                publication_calls.append(request)
                request_id = json.loads(request)["id"]
                return (
                    json.dumps(
                        {"jsonrpc": "2.0", "id": request_id, "result": {"content": []}},
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()

            server = HostMcpServer(runtime, publication_runner=publish)
            initialize = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "contract-test", "version": "1"},
                },
            }
            initialized = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
            list_tools = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }

            initialize_response = json.loads(
                server.handle_client_line((json.dumps(initialize) + "\n").encode())
            )
            self.assertEqual(
                initialize_response["result"]["protocolVersion"], "2025-06-18"
            )
            self.assertIn("tools", initialize_response["result"]["capabilities"])
            self.assertIsNone(
                server.handle_client_line((json.dumps(initialized) + "\n").encode())
            )
            tools_response = json.loads(
                server.handle_client_line((json.dumps(list_tools) + "\n").encode())
            )
            self.assertEqual(
                [tool["name"] for tool in tools_response["result"]["tools"]],
                ["upload_markdown"],
            )
            self.assertEqual(publication_calls, [])

            tool_call = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "upload_markdown",
                    "arguments": {"title": "Lazy", "markdownText": "# Lazy"},
                },
            }
            tool_response = json.loads(
                server.handle_client_line((json.dumps(tool_call) + "\n").encode())
            )

            self.assertEqual(tool_response["id"], 3)
            self.assertEqual(len(publication_calls), 1)

    def test_host_tool_contract_matches_the_container_annotations(self) -> None:
        self.assertEqual(UPLOAD_TOOL["name"], "upload_markdown")
        self.assertEqual(
            UPLOAD_TOOL["annotations"], tool_contracts()["upload_markdown"]
        )
        self.assertEqual(
            set(UPLOAD_TOOL["inputSchema"]["properties"]),
            {"title", "markdownText", "filePath"},
        )
        self.assertEqual(UPLOAD_TOOL["inputSchema"]["required"], ["title"])

    def test_publication_call_uses_one_ephemeral_hardened_container(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = DockerRuntime(
                image="remarkable-codex-mcp:0.3.0",
                state_volume="remarkable-publish-state-v1",
                artifact_host_directory=root / "artifacts",
                uid=501,
                gid=20,
            )
            request = {
                "jsonrpc": "2.0",
                "id": "publish-1",
                "method": "tools/call",
                "params": {
                    "name": "upload_markdown",
                    "arguments": {
                        "title": "One shot",
                        "markdownText": "# PRIVATE-BODY",
                    },
                },
            }
            observed: dict[str, object] = {}

            def exchange(
                args: list[str], payload: bytes, request_id: object
            ) -> bytes:
                observed["args"] = args
                observed["input"] = payload
                lines = payload.splitlines()
                internal_id = json.loads(lines[0])["id"]
                call_id = json.loads(lines[-1])["id"]
                self.assertEqual(request_id, call_id)
                self.assertTrue(internal_id.startswith("host-initialize-"))
                return (
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": call_id,
                            "result": {"content": [{"type": "text", "text": "ok"}]},
                        }
                    )
                    + "\n"
                ).encode()

            with (
                patch(
                    "remarkable_publish.docker_launcher._prepare_directories"
                ) as prepare,
                patch(
                    "remarkable_publish.docker_launcher._initialize_volume"
                ) as initialize_volume,
                patch(
                    "remarkable_publish.docker_launcher._exchange_with_container",
                    side_effect=exchange,
                ),
            ):
                response = _run_publication_call(
                    runtime, (json.dumps(request) + "\n").encode()
                )

            payload = json.loads(response)
            self.assertEqual(payload["id"], "publish-1")
            self.assertEqual(payload["result"]["content"][0]["text"], "ok")
            prepare.assert_called_once_with(runtime)
            initialize_volume.assert_called_once_with(runtime)
            args = observed["args"]
            self.assertIn("--rm", args)
            self.assertIn("--read-only", args)
            self.assertIn("remarkable-codex-mcp:0.3.0", args)
            joined = " ".join(args)
            self.assertNotIn("PRIVATE-BODY", joined)
            self.assertNotIn("One shot", joined)
            forwarded = observed["input"].splitlines()
            self.assertEqual(json.loads(forwarded[1])["method"], "notifications/initialized")
            self.assertEqual(json.loads(forwarded[2]), request)

    def test_publication_call_keeps_stdin_open_until_delayed_response(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = DockerRuntime(
                image="remarkable-codex-mcp:0.3.0",
                state_volume="remarkable-publish-state-v1",
                artifact_host_directory=Path(directory) / "artifacts",
                uid=501,
                gid=20,
            )
            request = {
                "jsonrpc": "2.0",
                "id": "delayed-response",
                "method": "tools/call",
                "params": {
                    "name": "upload_markdown",
                    "arguments": {"title": "Probe", "markdownText": ""},
                },
            }
            delayed_server = r'''
import json
import sys
import threading
import time

def respond(request):
    time.sleep(0.05)
    response = {
        "jsonrpc": "2.0",
        "id": request["id"],
        "result": {"content": [{"type": "text", "text": "validation-only"}]},
    }
    print(json.dumps(response, separators=(",", ":")), flush=True)

for line in sys.stdin:
    request = json.loads(line)
    if request.get("method") == "initialize":
        print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": {}}), flush=True)
    elif request.get("method") == "tools/call":
        threading.Thread(target=respond, args=(request,), daemon=True).start()
'''

            with (
                patch("remarkable_publish.docker_launcher._prepare_directories"),
                patch("remarkable_publish.docker_launcher._initialize_volume"),
                patch(
                    "remarkable_publish.docker_launcher.docker_run_args",
                    return_value=[sys.executable, "-u", "-c", delayed_server],
                ),
            ):
                response = _run_publication_call(
                    runtime, (json.dumps(request) + "\n").encode()
                )

            payload = json.loads(response)
            self.assertEqual(payload["id"], "delayed-response")
            self.assertEqual(
                payload["result"]["content"][0]["text"], "validation-only"
            )

    def test_publication_call_stages_only_the_requested_file_for_its_lifetime(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "private report.md"
            source.write_text("# DO-NOT-LEAK", encoding="utf-8")
            runtime = DockerRuntime(
                image="remarkable-codex-mcp:0.3.0",
                state_volume="remarkable-publish-state-v1",
                artifact_host_directory=root / "artifacts",
                uid=501,
                gid=20,
            )
            request = {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "upload_markdown",
                    "arguments": {"title": "Private", "filePath": str(source)},
                },
            }
            staged_directories: list[Path] = []

            def exchange(
                args: list[str], payload: bytes, request_id: object
            ) -> bytes:
                forwarded = json.loads(payload.splitlines()[-1])
                staged_path = Path(forwarded["params"]["arguments"]["filePath"])
                self.assertEqual(staged_path.parent, Path("/imports/0"))
                mount = next(
                    value
                    for value in args
                    if value.startswith("type=bind,") and "dst=/imports/0" in value
                )
                host_directory = Path(
                    next(part[4:] for part in mount.split(",") if part.startswith("src="))
                )
                staged_directories.append(host_directory)
                self.assertEqual(
                    (host_directory / staged_path.name).read_text(encoding="utf-8"),
                    "# DO-NOT-LEAK",
                )
                self.assertNotIn(str(source), " ".join(args))
                self.assertNotIn("DO-NOT-LEAK", " ".join(args))
                self.assertEqual(request_id, 9)
                return (
                    json.dumps(
                        {"jsonrpc": "2.0", "id": 9, "result": {"content": []}}
                    )
                    + "\n"
                ).encode()

            with (
                patch("remarkable_publish.docker_launcher._prepare_directories"),
                patch("remarkable_publish.docker_launcher._initialize_volume"),
                patch(
                    "remarkable_publish.docker_launcher._exchange_with_container",
                    side_effect=exchange,
                ),
            ):
                response = _run_publication_call(
                    runtime, (json.dumps(request) + "\n").encode()
                )

            self.assertEqual(json.loads(response)["id"], 9)
            self.assertEqual(len(staged_directories), 1)
            self.assertFalse(staged_directories[0].exists())

    def test_docker_start_failure_is_sanitized_as_a_tool_result(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = DockerRuntime(
                image="remarkable-codex-mcp:0.3.0",
                state_volume="remarkable-publish-state-v1",
                artifact_host_directory=Path(directory) / "artifacts",
                uid=501,
                gid=20,
            )
            request = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "upload_markdown",
                    "arguments": {"title": "Failure", "markdownText": "SECRET"},
                },
            }

            with (
                patch("remarkable_publish.docker_launcher._prepare_directories"),
                patch(
                    "remarkable_publish.docker_launcher._initialize_volume",
                    side_effect=OSError("SECRET /private/source"),
                ),
            ):
                response = _run_publication_call(
                    runtime, (json.dumps(request) + "\n").encode()
                )

            payload = json.loads(response)["result"]["structuredContent"]
            self.assertEqual(payload["errorCode"], "docker-launch-failed")
            self.assertNotIn("SECRET", response.decode())
            self.assertNotIn("/private/source", response.decode())

    def test_missing_docker_response_is_not_retry_safe(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = DockerRuntime(
                image="remarkable-codex-mcp:0.3.0",
                state_volume="remarkable-publish-state-v1",
                artifact_host_directory=Path(directory) / "artifacts",
                uid=501,
                gid=20,
            )
            request = {
                "jsonrpc": "2.0",
                "id": "missing-response",
                "method": "tools/call",
                "params": {
                    "name": "upload_markdown",
                    "arguments": {"title": "Failure", "markdownText": "SECRET"},
                },
            }

            with (
                patch("remarkable_publish.docker_launcher._prepare_directories"),
                patch("remarkable_publish.docker_launcher._initialize_volume"),
                patch(
                    "remarkable_publish.docker_launcher._exchange_with_container",
                    return_value=None,
                ),
            ):
                response = _run_publication_call(
                    runtime, (json.dumps(request) + "\n").encode()
                )

            failure = json.loads(response)["result"]["structuredContent"]
            self.assertEqual(failure["errorCode"], "docker-protocol-failed")
            self.assertEqual(failure["deliveryStatus"], "unknown")
            self.assertFalse(failure["retrySafe"])
            self.assertNotIn("SECRET", response.decode())

    def test_default_artifact_directory_uses_the_sandbox_writable_temp_root(self) -> None:
        with TemporaryDirectory() as directory:
            temp_root = Path(directory)
            with patch.dict(
                os.environ,
                {"TMPDIR": str(temp_root)},
                clear=True,
            ):
                runtime = _runtime()

            self.assertEqual(
                runtime.artifact_host_directory,
                temp_root / "remarkable-publish" / "artifacts",
            )

    def test_explicit_artifact_directory_overrides_the_temp_root(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            explicit = root / "durable-artifacts"
            with patch.dict(
                os.environ,
                {
                    "TMPDIR": str(root / "temporary"),
                    "REMARKABLE_ARTIFACT_HOST_DIR": str(explicit),
                },
                clear=True,
            ):
                runtime = _runtime()

            self.assertEqual(runtime.artifact_host_directory, explicit)

    def test_stdio_container_is_hardened_and_mounts_only_declared_paths(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "artifacts"
            staging = root / "staging"
            artifacts.mkdir()
            staging.mkdir()
            runtime = DockerRuntime(
                image="remarkable-codex-mcp:0.3.0",
                state_volume="remarkable-publish-state-v1",
                artifact_host_directory=artifacts,
                uid=501,
                gid=20,
            )

            args = docker_run_args(
                runtime,
                command=("remarkable-publish-mcp",),
                staging_host_directory=staging,
            )

            joined = " ".join(args)
            self.assertIn("--read-only", args)
            self.assertIn("--cap-drop=ALL", args)
            self.assertIn("--security-opt=no-new-privileges", args)
            self.assertIn("--user", args)
            self.assertIn("501:20", args)
            self.assertIn("type=volume,src=remarkable-publish-state-v1", joined)
            self.assertIn(f"src={artifacts.resolve()},dst=/artifacts", joined)
            self.assertIn(f"src={staging.resolve()},dst=/imports/0,readonly", joined)
            self.assertIn("REMARKABLE_IMPORT_ROOTS=/imports/0", args)
            self.assertNotIn("REMARKABLE_IMPORT_HOST_ROOTS", joined)
            self.assertNotIn("docker.sock", joined)
            self.assertNotIn("--publish", args)
            self.assertNotIn("-p", args)

    def test_removed_publish_mode_environment_is_not_forwarded(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            runtime = DockerRuntime(
                image="remarkable-codex-mcp:0.3.0",
                state_volume="remarkable-publish-state-v1",
                artifact_host_directory=artifacts,
                uid=501,
                gid=20,
            )

            args = docker_run_args(runtime, command=("remarkable-publish-mcp",))

            self.assertNotIn("REMARKABLE_BACKEND", " ".join(args))
            self.assertNotIn("REMARKABLE_EXPERIMENTAL_SIMPLE_UPLOAD", " ".join(args))
            self.assertNotIn("REMARKABLE_DEVICE_TOKEN", " ".join(args))

    def test_file_path_is_staged_without_forwarding_the_host_path_or_body(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            staging = root / "staging"
            staging.mkdir(mode=0o700)
            source = root / "private report.md"
            body = "# Private report\n\nSensitive body."
            source.write_text(body, encoding="utf-8")
            broker = FilePathBroker(staging)
            request = {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "upload_markdown",
                    "arguments": {"title": "Private", "filePath": str(source)},
                },
            }

            decision = broker.handle_client_line(
                (json.dumps(request, separators=(",", ":")) + "\n").encode()
            )

            self.assertIsNone(decision.response)
            self.assertIsNotNone(decision.forward)
            forwarded = json.loads(decision.forward)
            staged_path = forwarded["params"]["arguments"]["filePath"]
            self.assertRegex(staged_path, r"^/imports/0/[a-f0-9-]+\.md$")
            self.assertNotIn(str(source).encode(), decision.forward)
            self.assertNotIn(body.encode(), decision.forward)
            staged = staging / Path(staged_path).name
            self.assertEqual(staged.read_text(encoding="utf-8"), body)
            self.assertEqual(staged.stat().st_mode & 0o777, 0o600)

            response = b'{"jsonrpc":"2.0","id":7,"result":{}}\n'
            self.assertEqual(broker.handle_server_line(response), response)
            self.assertFalse(staged.exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are not available")
    def test_file_path_broker_rejects_symlinks_without_forwarding_content(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            staging = root / "staging"
            staging.mkdir(mode=0o700)
            source = root / "source.md"
            source.write_text("DO-NOT-LEAK", encoding="utf-8")
            link = root / "link.md"
            link.symlink_to(source)
            broker = FilePathBroker(staging)
            request = {
                "jsonrpc": "2.0",
                "id": "symlink",
                "method": "tools/call",
                "params": {
                    "name": "upload_markdown",
                    "arguments": {"title": "Private", "filePath": str(link)},
                },
            }

            decision = broker.handle_client_line((json.dumps(request) + "\n").encode())

            self.assertIsNone(decision.forward)
            payload = json.loads(decision.response)
            failure = payload["result"]["structuredContent"]
            self.assertEqual(failure["errorCode"], "invalid-publish-request")
            self.assertIn("symlink", failure["message"].lower())
            self.assertNotIn("DO-NOT-LEAK", decision.response.decode())
            self.assertNotIn(str(link), decision.response.decode())
            self.assertEqual(list(staging.iterdir()), [])

    def test_file_path_broker_rejects_sources_over_ten_megabytes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            staging = root / "staging"
            staging.mkdir(mode=0o700)
            source = root / "large.md"
            source.write_bytes(b"x" * (MAX_MARKDOWN_BYTES + 1))
            broker = FilePathBroker(staging)
            request = {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "upload_markdown",
                    "arguments": {"title": "Large", "filePath": str(source)},
                },
            }

            decision = broker.handle_client_line((json.dumps(request) + "\n").encode())

            self.assertIsNone(decision.forward)
            failure = json.loads(decision.response)["result"]["structuredContent"]
            self.assertIn("10 MB", failure["message"])
            self.assertEqual(list(staging.iterdir()), [])

    def test_file_path_broker_rejects_dual_sources_without_forwarding_private_data(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            staging = root / "staging"
            staging.mkdir(mode=0o700)
            source = root / "private report.md"
            source.write_text("DO-NOT-FORWARD", encoding="utf-8")
            broker = FilePathBroker(staging)
            request = {
                "jsonrpc": "2.0",
                "id": "dual-source",
                "method": "tools/call",
                "params": {
                    "name": "upload_markdown",
                    "arguments": {
                        "title": "Private",
                        "filePath": str(source),
                        "markdownText": "PRIVATE-INLINE-BODY",
                    },
                },
            }

            decision = broker.handle_client_line((json.dumps(request) + "\n").encode())

            self.assertIsNone(decision.forward)
            failure = json.loads(decision.response)["result"]["structuredContent"]
            self.assertEqual(failure["errorCode"], "invalid-publish-request")
            self.assertNotIn(str(source), decision.response.decode())
            self.assertNotIn("PRIVATE-INLINE-BODY", decision.response.decode())
            self.assertEqual(list(staging.iterdir()), [])

    def test_inline_markdown_and_unrelated_protocol_messages_pass_through(self) -> None:
        with TemporaryDirectory() as directory:
            broker = FilePathBroker(Path(directory))
            for message in (
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "upload_markdown",
                        "arguments": {"title": "Inline", "markdownText": "# Inline"},
                    },
                },
            ):
                line = (json.dumps(message) + "\n").encode()
                decision = broker.handle_client_line(line)
                self.assertEqual(decision.forward, line)
                self.assertIsNone(decision.response)


if __name__ == "__main__":
    unittest.main()
