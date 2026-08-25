from __future__ import annotations

import json
from pathlib import Path
import tomllib
import unittest

from remarkable_publish import __version__
from remarkable_publish.docker_launcher import DEFAULT_IMAGE


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_VERSION = "0.3.0"


class PluginContractTests(unittest.TestCase):
    def test_manifest_discovers_the_skill_and_bundled_mcp_server(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "remarkable-codex")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")
        self.assertNotIn("apps", manifest)
        self.assertNotIn("hooks", manifest)

    def test_bundled_mcp_uses_plugin_relative_launcher_without_secrets(self) -> None:
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(set(config), {"mcpServers"})
        self.assertEqual(set(config["mcpServers"]), {"remarkable-publisher"})
        server = config["mcpServers"]["remarkable-publisher"]

        self.assertEqual(server["command"], "python3")
        self.assertEqual(
            server["args"],
            ["src/remarkable_publish/docker_launcher.py", "serve"],
        )
        self.assertEqual(server["cwd"], ".")
        self.assertNotIn("env", server)
        self.assertTrue((ROOT / server["args"][0]).is_file())

        skill = (ROOT / "skills/export-summary-to-remarkable/SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Call `upload_markdown`", skill)
        self.assertIn("search for the exact tool name `upload_markdown`", skill)
        self.assertIn("Only report the bundled MCP server unavailable after", skill)
        self.assertIn("Docker is not required for tool discovery", skill)
        self.assertIn("For `docker-launch-failed` or `docker-protocol-failed`", skill)
        self.assertIn("any host-readable regular file", skill)
        self.assertNotIn("approved import roots", skill)
        self.assertNotIn("separately configured MCP server", skill)
        self.assertNotIn("dryRun", skill)
        self.assertNotIn("confirmUpload", skill)
        self.assertNotIn("dry-run", skill.lower())

    def test_plugin_package_and_image_share_the_contract_version(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertEqual(manifest["version"].split("+", 1)[0], CONTRACT_VERSION)
        self.assertEqual(project["project"]["version"], CONTRACT_VERSION)
        self.assertEqual(__version__, CONTRACT_VERSION)
        self.assertEqual(DEFAULT_IMAGE, f"remarkable-codex-mcp:{CONTRACT_VERSION}")
        self.assertIn(f'"remarkable-publish[mcp]=={CONTRACT_VERSION}"', dockerfile)
        self.assertIn(f"REMARKABLE_IMAGE_VERSION={CONTRACT_VERSION}", dockerfile)
        self.assertIn(f"remarkable-codex-mcp:{CONTRACT_VERSION}", readme)
        self.assertNotIn("remarkable-codex-mcp:0.2.0", readme)


if __name__ == "__main__":
    unittest.main()
