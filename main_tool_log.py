# -*- coding: utf-8 -*-
"""Tofanari Main Tool — simple logging for debugging during testing."""

import os
from datetime import datetime


def _log_path():
    from config import get_settings_dir

    return os.path.join(get_settings_dir(), "main_tool.log")


def _ensure_dir():
    p = _log_path()
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    return p


def log_import(book_code: str, chapter_code: str, markers_count: int, mp3_matched: int = 0):
    """Log when a chapter is imported (Ready PDF association)."""
    try:
        path = _ensure_dir()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = (
            f"[{ts}] IMPORT | book={book_code} | chapter={chapter_code} | "
            f"markers={markers_count} | mp3_matched={mp3_matched}\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
