import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pypdf import PdfReader

from remarkable_publish.cli import run


class CliTests(unittest.TestCase):
    def test_doctor_returns_one_json_result(self) -> None:
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = run(["--config", "missing.toml", "doctor"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout.getvalue())["ok"])

    def test_upload_renders_markdown_to_pdf_dry_run(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            imports = root / "imports"
            imports.mkdir()
            target = imports / "brief.md"
            target.write_text("# Brief\n\nHello from Markdown.", encoding="utf-8")
            config = root / "config.toml"
            config.write_text(f'[publish]\nimport_roots=["{imports}"]\nartifact_directory="{root / "artifacts"}"\nstate_directory="{root / "state"}"\n', encoding="utf-8")
            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                code = run(["--config", str(config), "upload", str(target), "--title", "Brief"])
            result = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(result["artifactMimeType"], "application/pdf")
            self.assertGreaterEqual(len(PdfReader(result["artifactPath"]).pages), 1)


if __name__ == "__main__":
    unittest.main()
