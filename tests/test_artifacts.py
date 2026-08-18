from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from pypdf import PdfReader

from remarkable_publish.artifacts import ArtifactStore, PDF_MIME


class ArtifactTests(unittest.TestCase):
    def test_markdown_is_rendered_to_a_content_addressed_pdf(self) -> None:
        with TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory) / "artifacts", host_root=Path("/host/artifacts"))
            first = store.render_markdown("# Heading\n\nHello **paper**.")
            second = store.render_markdown("# Heading\n\nHello **paper**.")
            self.assertEqual(first.sha256, second.sha256)
            self.assertEqual(first.mime_type, PDF_MIME)
            self.assertEqual(first.host_path, Path("/host/artifacts") / f"{first.artifact_id}.pdf")
            self.assertGreaterEqual(len(PdfReader(first.internal_path).pages), 1)

    def test_supported_markdown_link_creates_a_pdf_link_annotation(self) -> None:
        with TemporaryDirectory() as directory:
            artifact = ArtifactStore(Path(directory) / "artifacts").render_markdown(
                "Read the [runbook](https://example.com/runbook?a=1&b=2)."
            )
            page = PdfReader(artifact.internal_path).pages[0]
            annotations = page.get("/Annots")
            self.assertIsNotNone(annotations)
            uris = [item.get_object()["/A"]["/URI"] for item in annotations]
            self.assertEqual(uris, ["https://example.com/runbook?a=1&b=2"])
            self.assertNotIn("[runbook]", page.extract_text())

    def test_unsupported_link_scheme_remains_literal_text(self) -> None:
        with TemporaryDirectory() as directory:
            artifact = ArtifactStore(Path(directory) / "artifacts").render_markdown(
                "[unsafe](javascript:alert)"
            )
            page = PdfReader(artifact.internal_path).pages[0]
            self.assertIsNone(page.get("/Annots"))
            self.assertIn("[unsafe](javascript:alert)", page.extract_text())

    def test_supported_unicode_round_trips_through_the_pdf(self) -> None:
        with TemporaryDirectory() as directory:
            artifact = ArtifactStore(Path(directory) / "artifacts").render_markdown(
                "Résumé — café"
            )
            rendered = "".join(
                page.extract_text() or "" for page in PdfReader(artifact.internal_path).pages
            )
            self.assertIn("Résumé — café", rendered)

    def test_unsupported_unicode_is_rejected_instead_of_silently_losing_glyphs(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "artifacts"
            with self.assertRaisesRegex(ValueError, "U\\+4F60"):
                ArtifactStore(root).render_markdown("你好")
            self.assertFalse(root.exists())

    def test_markdown_file_must_be_utf8_inside_approved_root(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = root / "allowed"
            allowed.mkdir()
            inside = allowed / "inside.anything"
            outside = root / "outside.md"
            invalid = allowed / "invalid.md"
            inside.write_text("# Inside", encoding="utf-8")
            outside.write_text("# Outside", encoding="utf-8")
            invalid.write_bytes(b"\xff")
            store = ArtifactStore(root / "artifacts", import_roots=(allowed,))
            self.assertEqual(store.render_markdown_file(inside).mime_type, PDF_MIME)
            with self.assertRaisesRegex(ValueError, "approved import root"):
                store.render_markdown_file(outside)
            with self.assertRaisesRegex(ValueError, "UTF-8 Markdown"):
                store.render_markdown_file(invalid)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO files are not available")
    def test_markdown_file_must_be_a_regular_file(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fifo = root / "source.md"
            os.mkfifo(fifo)
            store = ArtifactStore(root / "artifacts", import_roots=(root,))
            with self.assertRaisesRegex(ValueError, "regular file"):
                store.render_markdown_file(fifo)

if __name__ == "__main__":
    unittest.main()
