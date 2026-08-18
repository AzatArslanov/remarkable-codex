from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from remarkable_publish.config import load_settings
class ConfigTests(unittest.TestCase):
    def test_defaults_are_dry_run(self) -> None:
        settings = load_settings(Path("definitely-missing.toml"))
        self.assertEqual(settings.backend, "dry-run")

    def test_loads_simple_upload(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text('[publish]\nbackend="simple-upload"\nexperimental_simple_upload=true\n', encoding="utf-8")
            settings = load_settings(path)
        self.assertEqual(settings.backend, "simple-upload")
        self.assertTrue(settings.experimental_simple_upload)

    def test_rejects_unknown_backend(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text('[publish]\nbackend="unsupported-cloud"\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not installed"):
                load_settings(path)

    def test_rejects_non_boolean_experimental_opt_in(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                '[publish]\nbackend="simple-upload"\nexperimental_simple_upload="false"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must be a boolean"):
                load_settings(path)


if __name__ == "__main__":
    unittest.main()
