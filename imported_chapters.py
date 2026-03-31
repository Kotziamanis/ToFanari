# -*- coding: utf-8 -*-
"""ToFanari — Track imported chapters per book for merge/validation."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

# Stored in settings/imported_chapters.json (gitignored)
from config import get_settings_dir

DEFAULT_PATH = os.path.join(get_settings_dir(), "imported_chapters.json")


def _ensure_settings_dir() -> str:
    get_settings_dir()  # ensures folder exists
    return DEFAULT_PATH


def _norm_key(s: str) -> str:
    """Normalize book_slug key to uppercase for consistency."""
    return (s or "").strip().upper().replace("-", "_").replace("_", "-") or "default"


def _norm_chapter_code(s: str) -> str:
    """Normalize chapter code to uppercase."""
    return (s or "").strip().upper()


def load_imported_chapters(path: str = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load imported chapters from JSON. Keys are book_slug (normalized to uppercase).
    Values are lists of {"chapter_code", "chapter_order", "pdf_path"}.
    """
    p = path or _ensure_settings_dir()
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("books", data) if isinstance(data.get("books"), dict) else {}
        # Normalize keys to uppercase for consistency
        result: Dict[str, List[Dict[str, Any]]] = {}
        for k, v in raw.items():
            if isinstance(v, list):
                nk = _norm_key(k)
                result.setdefault(nk, []).extend(v)
        return result
    except Exception:
        return {}


def save_imported_chapters(data: Dict[str, List[Dict[str, Any]]], path: str = None) -> bool:
    """Save imported chapters to JSON."""
    p = path or _ensure_settings_dir()
    _ensure_settings_dir()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"books": data}, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def add_imported_chapter(book_slug: str, chapter_code: str, chapter_order: int, pdf_path: str) -> None:
    """Add one imported chapter. Uses book_slug as key (uppercase)."""
    data = load_imported_chapters()
    key = _norm_key(book_slug)
    ch_norm = _norm_chapter_code(chapter_code)
    entries = data.get(key, [])
    # Avoid duplicate chapter_code in same book
    entries = [e for e in entries if _norm_chapter_code(e.get("chapter_code") or "") != ch_norm]
    entries.append({"chapter_code": ch_norm, "chapter_order": chapter_order, "pdf_path": pdf_path})
    data[key] = entries
    save_imported_chapters(data)


def get_imported_chapter_codes(book_slug: str) -> List[str]:
    """Return list of imported chapter codes for a book (key normalized to uppercase)."""
    data = load_imported_chapters()
    key = _norm_key(book_slug)
    entries = data.get(key, [])
    return [_norm_chapter_code(e.get("chapter_code") or "") for e in entries if _norm_chapter_code(e.get("chapter_code") or "")]
