# -*- coding: utf-8 -*-
"""ToFanari — Excel database export for Bunny.net / FlipBuilder / production."""

import os
from typing import List, Tuple

from config import (
    DEFAULT_BOOK_CODE,
    DEFAULT_BUNNY_BASE_URL,
    USE_BOOK_SUBFOLDER,
)
from pdf_ops import Marker, get_active_markers

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

# Production-ready columns (with hymn assignment)
HEADERS = [
    "#",
    "Page",
    "Y",
    "Song Title",
    "Echos",
    "Section",
    "MP3 Code",
    "MP3 File",
    "Bunny URL",
    "Status",
    "Notes",
]


def get_mp3_code(code: str, index_1based: int) -> str:
    """Public: MP3 code e.g. AN01-001."""
    return _mp3_basename(code, index_1based)


def get_mp3_file(code: str, index_1based: int) -> str:
    """Public: MP3 filename e.g. AN01-001.mp3."""
    return _mp3_basename(code, index_1based) + ".mp3"


def get_mp3_url(
    base_url: str,
    code: str,
    index_1based: int,
) -> str:
    """Public: Bunny URL for MP3 file."""
    return _build_mp3_url(base_url, code, index_1based, USE_BOOK_SUBFOLDER)


def _mp3_basename(code: str, index_1based: int) -> str:
    """
    MP3 naming: BOOKCODE-NNN (e.g. AN01-001).
    If code empty, fallback to 001, 002 for compatibility.
    """
    num = f"{index_1based:03d}"
    code_clean = (code or "").strip()
    return f"{code_clean}-{num}" if code_clean else num


def _build_mp3_url(
    base_url: str,
    code: str,
    index_1based: int,
    use_book_subfolder: bool = USE_BOOK_SUBFOLDER,
) -> str:
    """
    Bunny URL: base/BOOKCODE/BOOKCODE-NNN.mp3 when use_book_subfolder else base/BOOKCODE-NNN.mp3.
    """
    base = base_url.rstrip("/")
    mp3_name = _mp3_basename(code, index_1based) + ".mp3"
    if use_book_subfolder and (code or "").strip():
        return f"{base}/{(code or '').strip()}/{mp3_name}"
    return f"{base}/{mp3_name}"


def _all_markers_sorted(markers: List[Marker]) -> List[Marker]:
    """All markers sorted by page, y (for export order and ID assignment)."""
    out = list(markers)
    out.sort(key=lambda m: (m.page, m.y))
    return out


def validate_mp3_files(
    mp3_folder: str,
    markers: List[Marker],
    code: str = DEFAULT_BOOK_CODE,
) -> List[str]:
    """
    Check that expected BOOKCODE-NNN.mp3 files exist in mp3_folder (current book only).
    Returns list of missing filenames. Empty list = all exist.
    """
    if not (code or "").strip():
        return []
    ordered = _all_markers_sorted(markers)
    expected = [_mp3_basename(code, i + 1) + ".mp3" for i in range(len(ordered))]
    missing = []
    for name in expected:
        path = os.path.join(mp3_folder, name)
        if not os.path.isfile(path):
            missing.append(name)
    return missing


def build_database_xlsx(
    folder: str,
    markers: List[Marker],
    code: str = DEFAULT_BOOK_CODE,
    bunny_base_url: str = DEFAULT_BUNNY_BASE_URL,
    use_book_subfolder: bool = USE_BOOK_SUBFOLDER,
    assignments: List[dict] = None,
) -> Tuple[str, int]:
    """
    Create production-ready database.xlsx with columns:
    #, Page, Y, Song Title, Echos, Section, MP3 Code, MP3 File, Bunny URL, Status, Notes.
    assignments: list of dicts with song_title, echos, section (optional status, notes). Uses "" and "TODO" if missing.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Buttons"

    header_fill = PatternFill("solid", fgColor="800000")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    header_align = Alignment(horizontal="center", vertical="center")

    for c, h in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align

    ordered = _all_markers_sorted(markers)
    base = (bunny_base_url or DEFAULT_BUNNY_BASE_URL).rstrip("/")
    code_clean = (code or "").strip() or "BOOK"

    for i, m in enumerate(ordered):
        mp3_code = _mp3_basename(code_clean, i + 1)
        mp3_file = mp3_code + ".mp3"
        mp3_url = _build_mp3_url(base, code_clean, i + 1, use_book_subfolder)
        a = (assignments or [{}])[i] if assignments and i < len(assignments) else {}
        song_title = (a.get("song_title") or "").strip() if isinstance(a.get("song_title"), str) else ""
        echos = (a.get("echos") or "").strip() if isinstance(a.get("echos"), str) else ""
        section = (a.get("section") or "").strip() if isinstance(a.get("section"), str) else ""
        status = (a.get("status") or "TODO").strip() if isinstance(a.get("status"), str) else "TODO"
        notes = (a.get("notes") or "").strip() if isinstance(a.get("notes"), str) else ""
        ws.append([
            i + 1,
            m.page,
            round(m.y, 1),
            song_title,
            echos,
            section,
            mp3_code,
            mp3_file,
            mp3_url,
            status,
            notes,
        ])

    for col in ws.columns:
        ws.column_dimensions[get_column_letter(col[0].column)].width = 18

    path = os.path.join(folder, "database.xlsx")
    wb.save(path)
    return path, len(ordered)


def preview_lines(
    markers: List[Marker],
    code: str = DEFAULT_BOOK_CODE,
    bunny_base_url: str = DEFAULT_BUNNY_BASE_URL,
    max_lines: int = 40,
) -> List[str]:
    """Text preview of database rows for the UI."""
    ordered = _all_markers_sorted(markers)
    base = bunny_base_url.rstrip("/")
    lines = [f"{'ID':<6}{'Page':<6}{'MP3_File':<18}MP3_URL", "─" * 72]
    for i, m in enumerate(ordered[: max_lines - 2]):
        mp3_file = _mp3_basename(code, i + 1) + ".mp3"
        url = _build_mp3_url(base, code, i + 1)
        lines.append(f"{i + 1:03d}   {m.page:<6}{mp3_file:<18}{url}")
    return lines
