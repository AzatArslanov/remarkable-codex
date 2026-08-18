from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from remarkable_publish.docker_launcher import DockerRuntime, docker_run_args


class DockerLauncherTests(unittest.TestCase):
    def test_stdio_container_is_hardened_and_mounts_only_declared_paths(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "artifacts"
            imports = root / "imports"
            artifacts.mkdir()
            imports.mkdir()
            runtime = DockerRuntime(
                image="remarkable-codex-mcp:0.2.0",
                state_volume="remarkable-publish-state-v1",
                artifact_host_directory=artifacts,
                import_host_directories=(imports,),
                uid=501,
                gid=20,
            )

            args = docker_run_args(runtime, command=("remarkable-publish-mcp",))

            joined = " ".join(args)
            self.assertIn("--read-only", args)
            self.assertIn("--cap-drop=ALL", args)
            self.assertIn("--security-opt=no-new-privileges", args)
            self.assertIn("--user", args)
            self.assertIn("501:20", args)
            self.assertIn("type=volume,src=remarkable-publish-state-v1", joined)
            self.assertIn(f"src={artifacts.resolve()},dst=/artifacts", joined)
            self.assertIn(f"src={imports.resolve()},dst=/imports/0,readonly", joined)
            self.assertNotIn("docker.sock", joined)
            self.assertNotIn("--publish", args)
            self.assertNotIn("-p", args)

    def test_live_publish_options_are_forwarded_from_an_explicit_allowlist(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            runtime = DockerRuntime(
                image="remarkable-codex-mcp:0.2.0",
                state_volume="remarkable-publish-state-v1",
                artifact_host_directory=artifacts,
                import_host_directories=(),
                uid=501,
                gid=20,
                publish_environment=(
                    ("REMARKABLE_BACKEND", "simple-upload"),
                    ("REMARKABLE_EXPERIMENTAL_SIMPLE_UPLOAD", "1"),
                ),
            )

            args = docker_run_args(runtime, command=("remarkable-publish-mcp",))

            for name, value in runtime.publish_environment:
                self.assertIn(f"{name}={value}", args)
            self.assertNotIn("REMARKABLE_DEVICE_TOKEN", " ".join(args))


if __name__ == "__main__":
    unittest.main()
