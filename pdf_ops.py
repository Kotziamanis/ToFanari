# -*- coding: utf-8 -*-
"""ToFanari — PDF operations: detect markers, apply buttons."""

from dataclasses import dataclass
from typing import Callable, List, Optional

from config import BTN_X, BTN_W, BTN_H, C_BTN, C_WHT, MARKER, WHITE_BG

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


def get_active_markers(markers: List[Marker]) -> List[Marker]:
    """Return sorted list of markers with keep=True."""
    active = [m for m in markers if m.keep]
    active.sort(key=lambda m: (m.page, m.y))
    return active


def _remove_white_bg(doc: "fitz.Document", page_index: int) -> None:
    """Strip the full-page white rectangle that Melodos adds."""
    for xref in doc[page_index].get_contents():
        raw = doc.xref_stream(xref).decode("latin-1")
        cleaned = WHITE_BG.sub("", raw)
        if cleaned != raw:
            doc.update_stream(xref, cleaned.encode("latin-1"))


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
    """Place numbered red buttons at each active marker and hide the ■."""
    keep = get_active_markers(markers)
    doc = fitz.open(pdf_in)

    for i, m in enumerate(keep):
        p = m.page - 1
        _remove_white_bg(doc, p)
        page = doc[p]
        by = m.y - 5

        # 1. Cover the ■ with white
        cover = fitz.Rect(m.x - 2, m.y - 2, m.x + 14, m.y + 14)
        page.draw_rect(cover, color=C_WHT, fill=C_WHT, width=0)

        # 2. Draw dark-red button on left margin
        btn = fitz.Rect(BTN_X, by, BTN_X + BTN_W, by + BTN_H)
        page.draw_rect(btn, color=C_BTN, fill=C_BTN, width=0)

        # 3. Number on button
        page.insert_text(
            (BTN_X + 2, by + 15),
            f"{i + 1:03d}",
            fontsize=9,
            color=(1, 1, 1),
        )

        if progress_cb:
            progress_cb(i + 1, len(keep))

    doc.save(pdf_out)
    doc.close()
    return len(keep)
