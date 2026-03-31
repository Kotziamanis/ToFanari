# -*- coding: utf-8 -*-
"""ToFanari — PDF operations: detect markers, apply buttons."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from config import BTN_X, BTN_W, BTN_H, C_BTN, C_WHT, MARKER, WHITE_BG

if TYPE_CHECKING:
    from PIL.Image import Image

try:
    import fitz
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pymupdf"])
    import fitz


@dataclass
class Marker:
    """A single ■ marker position in the PDF."""
    page: int
    x: float
    y: float
    rect: "fitz.Rect"
    keep: bool = True
    # 1-based sequential number assigned during normalization for active markers.
    # This is used for button text/exports; it may be missing when markers are loaded.
    number: Optional[int] = None


def format_number(n: int) -> str:
    """Format marker/MP3 numbers as 3 digits: 001, 002, 003."""
    return f"{n:03d}"


def extract_preview_text(pdf_path: str, marker: Marker, max_chars: int = 70) -> str:
    """
    Extract a short text snippet from the PDF near the marker position.
    Uses a small rect slightly below the marker, extending down and right.
    Returns cleaned text up to max_chars, or empty string if no text found.
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc[marker.page - 1]
        rect = fitz.Rect(marker.x, marker.y + 2, marker.x + 250, marker.y + 35)
        text = page.get_text("text", clip=rect)
        doc.close()
    except Exception:
        return ""
    cleaned = " ".join(text.replace("\r", "").replace("\n", " ").split())
    return cleaned[:max_chars].strip()


def extract_hymn_preview_lines(
    pdf_path: str, marker: Marker, max_lines: int = 5, max_chars_per_line: int = 80
) -> str:
    """
    Extract the first 2–5 lines of hymn text from the PDF for the given marker.
    Uses a rect below the marker (same page) to get only that hymn/section.
    Returns cleaned lines joined by newline, or empty string on failure.
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc[marker.page - 1]
        rect = fitz.Rect(marker.x, marker.y + 2, marker.x + 400, marker.y + 95)
        text = page.get_text("text", clip=rect)
        doc.close()
    except Exception:
        return ""
    lines = [
        " ".join(ln.replace("\r", "").split()).strip()
        for ln in text.split("\n")
        if ln.strip()
    ]
    result = []
    for ln in lines[:max_lines]:
        if len(ln) > max_chars_per_line:
            ln = ln[: max_chars_per_line - 1] + "…"
        result.append(ln)
    return "\n".join(result).strip()


def render_page_thumbnail(
    pdf_path: str, page_number: int, max_width: int = 230
) -> Optional["Image"]:
    """
    Render a PDF page as a thumbnail image.
    page_number is 1-based (actual PDF page). Returns PIL Image or None on failure.
    """
    if page_number < 1:
        return None
    try:
        from PIL import Image

        doc = fitz.open(pdf_path)
        page_idx = int(page_number) - 1
        if page_idx >= len(doc):
            doc.close()
            return None
        page = doc.load_page(page_idx)
        print(f"  render_page_thumbnail: page_number={page_number} page_idx={page_idx} loading page {page_idx + 1}")
        rect = page.rect
        zoom = max_width / rect.width if rect.width > max_width else 1.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        doc.close()
        mode = "RGBA" if pix.alpha else "RGB"
        img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
        if img.mode == "RGBA":
            img = img.convert("RGB")
        return img
    except Exception:
        return None


def get_active_markers(markers: List[Marker]) -> List[Marker]:
    """Return sorted list of markers with keep=True."""
    active = [m for m in markers if m.keep]
    active.sort(key=lambda m: (m.page, m.y))
    # Normalize numbering so it starts from the first active marker.
    for i, m in enumerate(active):
        if m.number is None or m.number <= 0:
            m.number = i + 1
    return active


def _remove_white_bg(doc: "fitz.Document", page_index: int) -> None:
    """Strip the full-page white rectangle that Melodos adds."""
    for xref in doc[page_index].get_contents():
        raw = doc.xref_stream(xref).decode("latin-1")
        cleaned = WHITE_BG.sub("", raw)
        if cleaned != raw:
            doc.update_stream(xref, cleaned.encode("latin-1"))


# Standalone text span that is exactly three digits (001 … 999) — hymn label in prepared PDFs
_NUMBER_LABEL_3_RE = re.compile(r"^\d{3}$")

# Hidden metadata span written by ToFanari when user places markers manually.
# This preserves the ORIGINAL clicked coordinates even though the visible "001" label is in the margin.
_TF_MARKER_META_PREFIX = "TFMK"  # ToFanari Marker
_TF_MARKER_META_RE = re.compile(
    r"^TFMK\s+(?P<num>\d{3})\s+(?P<x>\d+(?:\.\d+)?)\s+(?P<y>\d+(?:\.\d+)?)$"
)


def detect_numbered_markers_from_pdf(
    pdf_path: str,
    *,
    max_x_ratio: float = 0.28,
) -> List[Marker]:
    """
    Load markers from visible 3-digit labels already drawn in the PDF (e.g. red buttons "001", "002").
    Uses PyMuPDF text dict (span geometry + text). Does not search for ■.

    If any such labels appear in the left margin (x0 < page_width * max_x_ratio), only margin
    spans are kept (reduces false positives from body text). Otherwise all matching spans are used.

    Each Marker.number is set from the PDF text (1 … 999) so downstream code formats as 001, 002, …
    """
    doc = fitz.open(pdf_path)
    raw: List[tuple] = []
    try:
        for p in range(len(doc)):
            page = doc.load_page(p)
            pw = float(page.rect.width)
            if pw <= 0:
                continue
            d = page.get_text("dict")
            for block in d.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        txt = (span.get("text") or "").strip()
                        if not txt or not _NUMBER_LABEL_3_RE.fullmatch(txt):
                            continue
                        num = int(txt)
                        if num < 1 or num > 999:
                            continue
                        bbox = span.get("bbox")
                        if not bbox or len(bbox) < 4:
                            continue
                        x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                        rect = fitz.Rect(x0, y0, x1, y1)
                        raw.append((p + 1, x0, y0, rect, num, pw))
    finally:
        doc.close()

    if not raw:
        return []

    margin = [t for t in raw if t[1] < t[5] * max_x_ratio]
    use = margin if margin else raw

    markers: List[Marker] = []
    for page, x0, y0, rect, num, _pw in use:
        markers.append(
            Marker(page=page, x=x0, y=y0, rect=rect, keep=True, number=num)
        )
    markers.sort(key=lambda m: (m.page, m.y, m.x))
    return markers


def detect_tofanari_markers_from_pdf(pdf_path: str) -> List[Marker]:
    """
    Load ToFanari manual markers from hidden metadata spans.
    Falls back to [] if no metadata is present.

    Metadata format (span text, single span):
      "TFMK NNN X Y"
    Where:
      - NNN is 001..999
      - X, Y are original PDF coordinates in points (top-left origin, y down)
    """
    doc = fitz.open(pdf_path)
    found: List[Marker] = []
    try:
        for p in range(len(doc)):
            page = doc.load_page(p)
            d = page.get_text("dict")
            for block in d.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        txt = (span.get("text") or "").strip()
                        if not txt:
                            continue
                        m = _TF_MARKER_META_RE.fullmatch(txt)
                        if not m:
                            continue
                        try:
                            num = int(m.group("num"))
                            x = float(m.group("x"))
                            y = float(m.group("y"))
                        except Exception:
                            continue
                        if num < 1 or num > 999:
                            continue
                        rect = fitz.Rect(x, y, x + 1, y + 1)
                        found.append(Marker(page=p + 1, x=x, y=y, rect=rect, keep=True, number=num))
    finally:
        doc.close()
    found.sort(key=lambda mm: (mm.page, mm.number if mm.number else 10**9, mm.y, mm.x))
    return found


def markers_to_serializable_dicts(markers: List[Marker]) -> List[Dict[str, Any]]:
    """Active markers as plain dicts: id "001", page, x, y (for reports / JSON)."""
    active = [m for m in markers if m.keep]
    active.sort(key=lambda m: (m.page, m.y, m.x))
    out: List[Dict[str, Any]] = []
    for m in active:
        if m.number is None or not isinstance(m.number, int) or m.number <= 0:
            continue
        out.append({
            "id": format_number(m.number),
            "page": m.page,
            "x": round(float(m.x), 2),
            "y": round(float(m.y), 2),
        })
    return out


def detect_markers(pdf_path: str) -> List[Marker]:
    """Find all ■ characters in PDF, regardless of color."""
    doc = fitz.open(pdf_path)
    markers: List[Marker] = []
    for p in range(len(doc)):
        instances = doc[p].search_for(MARKER)
        for rect in instances:
            markers.append(
                Marker(
                    page=p + 1,
                    x=rect.x0,
                    y=rect.y0,
                    rect=rect,
                    keep=True,
                )
            )
    doc.close()
    markers.sort(key=lambda m: (m.page, m.y))
    return markers


def apply_markers(
    pdf_in: str,
    markers: List[Marker],
    pdf_out: str,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> int:
    """Place numbered red buttons at each active marker XY and hide the ■."""
    keep = get_active_markers(markers)
    doc = fitz.open(pdf_in)

    for m in keep:
        p = m.page - 1
        _remove_white_bg(doc, p)
        page = doc[p]
        by = m.y - 5

        # 1. Cover the ■ with white
        cover = fitz.Rect(m.x - 2, m.y - 2, m.x + 14, m.y + 14)
        page.draw_rect(cover, color=C_WHT, fill=C_WHT, width=0)

        # 2. Draw dark-red button at marker X/Y (no legacy fixed left margin)
        bx = float(m.x)
        btn = fitz.Rect(bx, by, bx + BTN_W, by + BTN_H)
        # Keep button fully inside page bounds.
        if btn.x1 > page.rect.width:
            shift = btn.x1 - float(page.rect.width)
            btn = fitz.Rect(btn.x0 - shift, btn.y0, btn.x1 - shift, btn.y1)
        if btn.x0 < 0:
            btn = fitz.Rect(0.0, btn.y0, BTN_W, btn.y1)
        page.draw_rect(btn, color=C_BTN, fill=C_BTN, width=0)

        # 3. Number on button
        page.insert_text(
            (btn.x0 + 2, by + 15),
            format_number(m.number if m.number is not None else 1),
            fontsize=9,
            color=(1, 1, 1),
        )

        if progress_cb:
            progress_cb(m.number if m.number is not None else 1, len(keep))

    doc.save(pdf_out)
    doc.close()
    return len(keep)


def embed_numbered_markers_pdf(
    pdf_in: str,
    markers: List[Marker],
    pdf_out: str,
    *,
    fontname: str = "helv",
    fontsize: float = 9.0,
) -> int:
    """
    Embed numbered marker labels (001, 002, …) in the left margin AND write hidden metadata
    so ToFanari can reload the original clicked marker coordinates later.

    Purpose: enable detect_numbered_markers_from_pdf() to load markers from the PDF without relying on ■.
    This does NOT draw red buttons; it only writes the numeric labels.
    """
    keep = get_active_markers(markers)
    doc = fitz.open(pdf_in)
    try:
        for m in keep:
            p = int(m.page) - 1
            if p < 0 or p >= len(doc):
                continue
            page = doc[p]
            y = float(m.y)
            # Keep label in margin (x0 < 0.28 * page_width) so the loader prefers margin-only spans.
            x = float(BTN_X + 2.0)
            # Insert baseline a bit below the marker y so it is visually readable.
            page.insert_text(
                (x, y + 15.0),
                format_number(int(m.number) if m.number else 1),
                fontsize=float(fontsize),
                fontname=fontname,
                color=(0, 0, 0),
            )
            # Hidden metadata: single-span token to preserve original X/Y.
            # White + tiny font makes it effectively invisible on white backgrounds.
            meta = f"{_TF_MARKER_META_PREFIX} {format_number(int(m.number) if m.number else 1)} {float(m.x):.2f} {float(m.y):.2f}"
            page.insert_text(
                (x, y + 6.0),
                meta,
                fontsize=1.0,
                fontname=fontname,
                color=(1, 1, 1),
            )
        doc.save(pdf_out, garbage=4, deflate=True)
    finally:
        doc.close()
    return len(keep)
