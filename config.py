# -*- coding: utf-8 -*-
"""Tofanari Main Tool — constants and configuration."""

import os
import re
import sys

APP_TITLE = "Tofanari Main Tool — Βυζαντινή Μουσική"


def get_settings_dir() -> str:
    """
    Single source for settings folder path.
    - EXE: folder next to executable (os.path.dirname(sys.executable) + /settings)
    - Dev: project root (os.path.dirname(__file__) + /settings)
    Creates folder if it does not exist.
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "settings")
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    return path

# Single source for app version. Change here to update UI, window title, status bar.
APP_VERSION = "v1.5.4-AUTO-MP3"
VERSION = APP_VERSION  # Alias for backward compatibility

# ─── Bunny.net / CDN (Digital Byzantine Music Publishing System) ───
BUNNY_BASE_URL = "https://fanari.b-cdn.net"
USE_BOOK_SUBFOLDER = True  # URL = base/BOOKCODE/BOOKCODE-NNN.mp3

# Chapter-level publishing (professional workflow)
# Bunny folder: {BUNNY_ROOT_FOLDER}/{book_slug}/{chapter_code}/CHAPTERCODE-NNN.mp3
BUNNY_ROOT_FOLDER = "books"

# CLI: python app.py prepare_bunny — scan/copy/rewrite (no upload)
SOURCE_BOOKS_ROOT = "source_books"
OUTPUT_READY_ROOT = "output_ready"

# Books under these slugs (or prefixes) are non-production; excluded from default upload selection.
_NON_PROD_SLUGS = frozenset(
    {"example_book", "demo", "test", "sample", "fixture", "sandbox", "placeholder"}
)
_NON_PROD_PREFIXES = ("example_", "test_", "demo_", "sample_", "mock_")


def is_production_book_slug(book_slug: str) -> bool:
    """True if book folder is treated as real production (not demo/example/test)."""
    s = (book_slug or "").strip().lower()
    if not s:
        return False
    if s in _NON_PROD_SLUGS:
        return False
    for p in _NON_PROD_PREFIXES:
        if s.startswith(p):
            return False
    return True

# Bunny Storage upload (CLI: python app.py upload_bunny)
# Credentials are entered via GUI/terminal dialog; saved to settings/bunny_credentials.json (gitignored).
# Fallback: env vars BUNNY_STORAGE_ZONE_NAME, BUNNY_STORAGE_API_KEY, etc. (for dry-run / scripts)
BUNNY_STORAGE_ZONE_NAME = (os.environ.get("BUNNY_STORAGE_ZONE_NAME") or "").strip()
BUNNY_STORAGE_API_KEY = (os.environ.get("BUNNY_STORAGE_API_KEY") or "").strip()
BUNNY_STORAGE_HOST = (os.environ.get("BUNNY_STORAGE_HOST") or "storage.bunnycdn.com").strip()
BUNNY_PUBLIC_BASE_URL = (os.environ.get("BUNNY_PUBLIC_BASE_URL") or "").strip() or None

# UI colors (hex)
DARK_RED = "#800000"
MID_RED = "#A00000"
LIGHT_RED = "#F2DCDB"
CREAM = "#FDF6F0"
GOLD = "#C8A85A"
WHITE = "#FFFFFF"
GREY_LIGHT = "#F5F5F5"
GREY_MED = "#CCCCCC"
TEXT_DARK = "#2C1810"
GREEN = "#2E7D32"

# Button geometry in PDF points
BTN_X = 28.3
BTN_W = 36
BTN_H = 22

# Colors as 0-1 RGB for PyMuPDF
C_BTN = (0.77, 0.12, 0.23)  # dark red
C_WHT = (1.0, 1.0, 1.0)     # white cover

# Marker character (■ U+25A0)
MARKER = "\u25a0"

# Regex to remove Melodos full-page white rectangle from PDF stream
WHITE_BG = re.compile(
    r"q\s+1\.0+ 1\.0+ 1\.0+ rg\s+0\.0+ 0\.0+ m"
    r"\s+[\d\. ]+l\s+[\d\. ]+l\s+[\d\. ]+l\s+h\s+f\s+Q"
)

# Excel / export defaults (override in GUI)
DEFAULT_BOOK_CODE = "BOOK"
DEFAULT_BUNNY_BASE_URL = BUNNY_BASE_URL
