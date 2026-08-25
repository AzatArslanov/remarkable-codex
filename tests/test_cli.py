import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from remarkable_publish.cli import run


class CliTests(unittest.TestCase):
    def test_doctor_returns_one_json_result(self) -> None:
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = run(["--config", "missing.toml", "doctor"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout.getvalue())["ok"])

    def test_upload_has_no_mode_switches_and_publishes_once(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "brief.md"
            target.write_text("# Brief\n\nHello from Markdown.", encoding="utf-8")
            config = root / "config.toml"
            config.write_text(f'[publish]\nartifact_directory="{root / "artifacts"}"\nstate_directory="{root / "state"}"\n', encoding="utf-8")
            stdout = io.StringIO()
            tools = Mock()
            tools.upload_markdown.return_value = {"ok": True, "artifactMimeType": "application/pdf"}
            with patch("sys.stdout", stdout), patch(
                "remarkable_publish.cli.RemarkableTools.from_settings", return_value=tools
            ):
                code = run(["--config", str(config), "upload", str(target), "--title", "Brief"])
            result = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(result["artifactMimeType"], "application/pdf")
            tools.upload_markdown.assert_called_once_with(
                markdown_text="# Brief\n\nHello from Markdown.", title="Brief"
            )

            with self.assertRaises(SystemExit):
                run(["upload", str(target), "--title", "Brief", "--live"])


if __name__ == "__main__":
    unittest.main()
