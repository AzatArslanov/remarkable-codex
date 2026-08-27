import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from remarkable_publish.config import load_settings


class ConfigTests(unittest.TestCase):
    def test_defaults_have_no_publish_mode(self) -> None:
        settings = load_settings(Path("definitely-missing.toml"))
        self.assertFalse(hasattr(settings, "backend"))
        self.assertFalse(hasattr(settings, "experimental_simple_upload"))

    def test_rejects_removed_publish_mode_options(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text('[publish]\nbackend="simple-upload"\nexperimental_simple_upload=true\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "removed publish option"):
                load_settings(path)


if __name__ == "__main__":
    unittest.main()
