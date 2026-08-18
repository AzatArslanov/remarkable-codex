from __future__ import annotations

from hashlib import sha256
from html import escape
from io import BytesIO
import os
from pathlib import Path
import re
import stat
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, XPreformatted

from .domain import RenderedArtifact


PDF_MIME = "application/pdf"
MAX_MARKDOWN_BYTES = 10 * 1024 * 1024
MAX_PDF_BYTES = 100 * 1024 * 1024
_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")


def validate_pdf(path: Path) -> None:
    try:
        size = path.stat().st_size
        if size <= 0 or size > MAX_PDF_BYTES:
            raise ValueError("file is not a valid PDF within the 100 MB limit")
        with path.open("rb") as handle:
            header = handle.read(8)
            handle.seek(max(0, size - 2048))
            trailer = handle.read()
        if not header.startswith(b"%PDF-") or b"%%EOF" not in trailer:
            raise ValueError("file is not a valid PDF")
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted:
            raise ValueError("encrypted PDFs are not supported")
        len(reader.pages)
    except (OSError, PdfReadError, TypeError, ValueError) as error:
        raise ValueError("file is not a valid PDF") from error


def _register_fonts() -> tuple[str, str, str]:
    regular, bold, mono = "RemarkableVera", "RemarkableVeraBold", "RemarkableVeraMono"
    font_dir = Path(__import__("reportlab").__file__).parent / "fonts"
    for name, filename in (
        (regular, "Vera.ttf"),
        (bold, "VeraBd.ttf"),
        (mono, "Vera.ttf"),
    ):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, font_dir / filename))
    pdfmetrics.registerFontFamily(regular, normal=regular, bold=bold)
    return regular, bold, mono


def _styled_text(value: str) -> str:
    value = escape(value)
    value = re.sub(r"`([^`]+)`", r'<font name="RemarkableVeraMono">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*|__([^_]+)__", lambda match: f"<b>{match.group(1) or match.group(2)}</b>", value)
    return re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)|(?<!_)_([^_]+)_(?!_)", lambda match: f"<i>{match.group(1) or match.group(2)}</i>", value)


def _inline(value: str) -> str:
    rendered: list[str] = []
    offset = 0
    for match in _LINK.finditer(value):
        rendered.append(_styled_text(value[offset : match.start()]))
        label, target = match.groups()
        try:
            supported = urlsplit(target).scheme.lower() in {"http", "https", "mailto"}
        except ValueError:
            supported = False
        if supported:
            rendered.append(
                f'<a href="{escape(target, quote=True)}" color="#1f4e79">'
                f"{_styled_text(label)}</a>"
            )
        else:
            rendered.append(_styled_text(match.group(0)))
        offset = match.end()
    rendered.append(_styled_text(value[offset:]))
    return "".join(rendered)


def _validate_font_coverage(markdown_text: str, font_names: tuple[str, ...]) -> None:
    coverage = [pdfmetrics.getFont(name).face.charToGlyph for name in font_names]
    unsupported = sorted(
        {
            ord(character)
            for character in markdown_text
            if character not in "\r\n\t"
            and not all(ord(character) in character_map for character_map in coverage)
        }
    )
    if unsupported:
        sample = ", ".join(f"U+{codepoint:04X}" for codepoint in unsupported[:8])
        suffix = " and more" if len(unsupported) > 8 else ""
        raise ValueError(f"Markdown contains characters unsupported by embedded PDF fonts: {sample}{suffix}")


def _table(lines: list[str], body_style: ParagraphStyle) -> Table:
    rows = [[Paragraph(_inline(cell.strip()), body_style) for cell in line.strip().strip("|").split("|")] for line in lines]
    table = Table(rows, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "RemarkableVeraBold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ececec")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#777777")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def render_markdown_pdf(markdown_text: str) -> bytes:
    encoded = markdown_text.encode("utf-8")
    if not encoded or len(encoded) > MAX_MARKDOWN_BYTES:
        raise ValueError("Markdown source must be non-empty and no larger than 10 MB")
    regular, bold, mono = _register_fonts()
    _validate_font_coverage(markdown_text, (regular, bold, mono))
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontName=regular, fontSize=10.5, leading=15, spaceAfter=7)
    code = ParagraphStyle("Code", parent=body, fontName=mono, fontSize=8.5, leading=11, leftIndent=8, rightIndent=8, backColor=colors.HexColor("#f3f3f3"), borderPadding=6)
    quote = ParagraphStyle("Quote", parent=body, leftIndent=12, textColor=colors.HexColor("#444444"), borderPadding=5)
    heading_sizes = {1: 22, 2: 17, 3: 14, 4: 12, 5: 11, 6: 10}
    headings = {level: ParagraphStyle(f"H{level}", parent=body, fontName=bold, fontSize=size, leading=size + 4, spaceBefore=10, spaceAfter=6, keepWithNext=True) for level, size in heading_sizes.items()}
    story: list = []
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    index = 0
    pending: list[str] = []

    def flush() -> None:
        if pending:
            story.append(Paragraph(_inline(" ".join(part.strip() for part in pending)), body))
            pending.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            index += 1
            block: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index])
                index += 1
            story.append(XPreformatted(escape("\n".join(block)), code))
        elif not stripped:
            flush()
        elif match := re.match(r"^(#{1,6})\s+(.+)$", stripped):
            flush()
            story.append(Paragraph(_inline(match.group(2)), headings[len(match.group(1))]))
        elif index + 1 < len(lines) and "|" in line and re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1]):
            flush()
            table_lines = [line]
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                table_lines.append(lines[index])
                index += 1
            index -= 1
            story.extend((_table(table_lines, body), Spacer(1, 7)))
        elif re.match(r"^\s*[-+*]\s+", line):
            flush()
            items: list[ListItem] = []
            while index < len(lines) and (item := re.match(r"^\s*[-+*]\s+(.+)$", lines[index])):
                items.append(ListItem(Paragraph(_inline(item.group(1)), body)))
                index += 1
            index -= 1
            story.extend((ListFlowable(items, bulletType="bullet", leftIndent=18, bulletFontName=regular), Spacer(1, 4)))
        elif re.match(r"^\s*\d+[.)]\s+", line):
            flush()
            numbered: list[ListItem] = []
            while index < len(lines) and (item := re.match(r"^\s*\d+[.)]\s+(.+)$", lines[index])):
                numbered.append(ListItem(Paragraph(_inline(item.group(1)), body)))
                index += 1
            index -= 1
            story.extend((ListFlowable(numbered, bulletType="1", leftIndent=22, bulletFontName=regular), Spacer(1, 4)))
        elif stripped.startswith(">"):
            flush()
            story.append(Paragraph(_inline(stripped.lstrip("> ")), quote))
        else:
            pending.append(line)
        index += 1
    flush()
    if not story:
        raise ValueError("Markdown source must contain renderable text")
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title="Markdown document", author="remarkable-publish")
    def deterministic_canvas(*args, **kwargs):
        kwargs["invariant"] = 1
        return Canvas(*args, **kwargs)

    document.build(story, canvasmaker=deterministic_canvas)
    return output.getvalue()


class ArtifactStore:
    def __init__(self, root: Path, *, host_root: Path | None = None, import_roots: tuple[Path, ...] = (), import_host_roots: tuple[Path, ...] = ()) -> None:
        if import_host_roots and len(import_host_roots) != len(import_roots):
            raise ValueError("host and container import roots must have the same length")
        self.root, self.host_root = root, host_root or root
        self.import_roots = tuple(path.resolve() for path in import_roots)
        self.import_host_roots = tuple(path.resolve() for path in import_host_roots)

    def _metadata(self, path: Path) -> RenderedArtifact:
        digest = sha256(path.read_bytes()).hexdigest()
        return RenderedArtifact(f"pdf-{digest}", path, self.host_root / path.name, path.stat().st_size, digest, PDF_MIME)

    def render_markdown(self, markdown_text: str) -> RenderedArtifact:
        try:
            pdf = render_markdown_pdf(markdown_text)
        except ValueError:
            raise
        except Exception as error:
            raise ValueError("Markdown could not be rendered") from error
        self.root.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=self.root, prefix=".incoming-", suffix=".pdf", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(pdf)
        try:
            validate_pdf(temporary)
            digest = sha256(pdf).hexdigest()
            target = self.root / f"pdf-{digest}.pdf"
            if not target.exists():
                os.replace(temporary, target)
            return self._metadata(target)
        finally:
            temporary.unlink(missing_ok=True)

    def _map_host_import(self, path: Path) -> Path:
        if not self.import_host_roots:
            return path
        candidate = path.expanduser().resolve()
        for host_root, container_root in zip(self.import_host_roots, self.import_roots):
            if candidate.is_relative_to(host_root):
                return container_root / candidate.relative_to(host_root)
        return path

    def render_markdown_file(self, path: Path) -> RenderedArtifact:
        candidate = self._map_host_import(path).expanduser().resolve()
        if not any(candidate.is_relative_to(root) for root in self.import_roots):
            raise ValueError("Markdown path is outside every approved import root")
        descriptor: int | None = None
        try:
            flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(candidate, flags)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("Markdown path must identify a regular file")
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = None
                encoded = handle.read(MAX_MARKDOWN_BYTES + 1)
            if len(encoded) > MAX_MARKDOWN_BYTES:
                raise ValueError("Markdown source must be no larger than 10 MB")
            source = encoded.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("file is not valid UTF-8 Markdown") from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
        return self.render_markdown(source)
