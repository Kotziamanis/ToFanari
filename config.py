# -*- coding: utf-8 -*-
"""ToFanari — Constants and configuration."""

import re

APP_TITLE = "ToFanari — Βυζαντινή Μουσική"
VERSION = "v3.0"

# ─── Bunny.net / CDN (Digital Byzantine Music Publishing System) ───
BUNNY_BASE_URL = "https://fanari.b-cdn.net"
USE_BOOK_SUBFOLDER = True  # URL = base/BOOKCODE/BOOKCODE-NNN.mp3

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
