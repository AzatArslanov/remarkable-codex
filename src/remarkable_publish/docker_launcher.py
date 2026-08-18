from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys


DEFAULT_IMAGE = "remarkable-codex-mcp:0.2.0"
DEFAULT_STATE_VOLUME = "remarkable-publish-state-v1"


@dataclass(frozen=True, slots=True)
class DockerRuntime:
    image: str
    state_volume: str
    artifact_host_directory: Path
    import_host_directories: tuple[Path, ...]
    uid: int
    gid: int
    publish_environment: tuple[tuple[str, str], ...] = ()


def _mount(kind: str, source: str, destination: str, *, readonly: bool = False) -> str:
    value = f"type={kind},src={source},dst={destination}"
    return f"{value},readonly" if readonly else value


def docker_run_args(
    runtime: DockerRuntime,
    *,
    command: tuple[str, ...],
    tty: bool = False,
) -> list[str]:
    artifacts = runtime.artifact_host_directory.resolve()
    imports = tuple(path.resolve() for path in runtime.import_host_directories)
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
    for name, value in runtime.publish_environment:
        args.extend(["--env", f"{name}={value}"])
    if tty:
        args.insert(args.index("--init"), "-t")
    container_roots: list[str] = []
    host_roots: list[str] = []
    for index, path in enumerate(imports):
        destination = f"/imports/{index}"
        args.extend(["--mount", _mount("bind", str(path), destination, readonly=True)])
        container_roots.append(destination)
        host_roots.append(str(path))
    args.extend(
        [
            "--env",
            f"REMARKABLE_IMPORT_ROOTS={os.pathsep.join(container_roots)}",
            "--env",
            f"REMARKABLE_IMPORT_HOST_ROOTS={os.pathsep.join(host_roots)}",
            runtime.image,
            *command,
        ]
    )
    return args


def _runtime() -> DockerRuntime:
    artifact_directory = Path(
        os.environ.get(
            "REMARKABLE_ARTIFACT_HOST_DIR",
            str(Path.home() / ".local/share/remarkable-publish/artifacts"),
        )
    ).expanduser()
    configured_imports = os.environ.get("REMARKABLE_IMPORT_HOST_ROOTS")
    import_directories = (
        tuple(Path(item).expanduser() for item in configured_imports.split(os.pathsep) if item)
        if configured_imports
        else (Path.home() / "Documents/Remarkable Imports",)
    )
    allowed_publish_environment = tuple(
        (name, os.environ[name])
        for name in (
            "REMARKABLE_BACKEND",
            "REMARKABLE_EXPERIMENTAL_SIMPLE_UPLOAD",
        )
        if name in os.environ
    )
    return DockerRuntime(
        image=os.environ.get("REMARKABLE_MCP_IMAGE", DEFAULT_IMAGE),
        state_volume=os.environ.get("REMARKABLE_STATE_VOLUME", DEFAULT_STATE_VOLUME),
        artifact_host_directory=artifact_directory,
        import_host_directories=import_directories,
        uid=os.getuid(),
        gid=os.getgid(),
        publish_environment=allowed_publish_environment,
    )


def _prepare_directories(runtime: DockerRuntime) -> None:
    for path in (runtime.artifact_host_directory, *runtime.import_host_directories):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path, 0o700)


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
            raise SystemExit(_run_container(runtime, ("remarkable-publish-mcp",)))
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
