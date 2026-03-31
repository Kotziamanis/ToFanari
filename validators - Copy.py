# -*- coding: utf-8 -*-
"""ToFanari — Validation helpers for single-book production."""

from typing import List, Tuple

from pdf_ops import Marker

from database import validate_mp3_files as _validate_mp3_files


def validate_empty_book_code(code: str) -> Tuple[bool, str]:
    """
    Book code is required for production export (BOOKCODE-NNN.mp3, Bunny URL).
    Returns (ok, message). ok=False if code is empty or only whitespace.
    """
    if not (code or "").strip():
        return False, "Ο Κωδικός Βιβλίου είναι υποχρεωτικός (π.χ. AN01)."
    return True, ""


def validate_duplicate_positions(markers: List[Marker]) -> Tuple[bool, str]:
    """Warn if two markers have same (page, y). Returns (ok, message)."""
    seen = set()
    for m in markers:
        key = (m.page, round(m.y, 1))
        if key in seen:
            return False, f"Διπλότυπη θέση: Σελίδα {m.page}, Y≈{m.y:.0f}."
        seen.add(key)
    return True, ""


def validate_page_numbers(markers: List[Marker], max_page: int = 9999) -> Tuple[bool, str]:
    """Page numbers must be positive and not exceed max_page."""
    for m in markers:
        if not (1 <= m.page <= max_page):
            return False, f"Μη έγκυρη σελίδα: {m.page} (marker στο Y={m.y:.0f})."
    return True, ""


def validate_missing_mp3(
    mp3_folder: str,
    markers: List[Marker],
    code: str,
) -> Tuple[bool, List[str]]:
    """
    Check that all expected BOOKCODE-NNN.mp3 exist in mp3_folder.
    Returns (ok, list_of_missing). ok=True when list is empty.
    """
    if not mp3_folder or not (code or "").strip():
        return True, []
    missing = _validate_mp3_files(mp3_folder, markers, code)
    return (len(missing) == 0, missing)
