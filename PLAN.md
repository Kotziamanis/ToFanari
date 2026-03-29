# ToFanari v3 — Plan (@ context, / commands)

## Context (@)

| @ | Role |
|---|------|
| @config.py | VERSION, BUNNY_BASE_URL, USE_BOOK_SUBFOLDER, BTN_X/W/H, DEFAULT_BUNNY_BASE_URL |
| @database.py | Production Excel (ID, Page, X, Y, Width, Height, MP3_File, MP3_URL, Active, First_Words, Notes), Bunny URL per book, validate_mp3_files |
| @pdf_ops.py | Marker, detect_markers, apply_markers — **unchanged** (no edits) |
| @validators.py | validate_empty_book_code, validate_duplicate_positions, validate_page_numbers, validate_missing_mp3 |
| @app.py | Tabs 1–4, Book Code, Bunny URL, MP3 folder, Validate MP3, _gen_db with validators |
| @tofanari_v21.py | Entry point: runs App |

## Commands (/)

| / | Purpose |
|---|--------|
| `/python tofanari_v21.py` | Run app from project root |
| `/cd c:\Users\User\ToFanari_v4` | Project root (before run) |
| `/pip install pymupdf openpyxl` | One-time deps (or auto on first import) |

## Single-book workflow (no batch)

1. Tab 1: Set **Φάκελος εργασίας**, open **PDF** (@app.py Tab 1).
2. Tab 2: **Εντοπισμός Markers** → @pdf_ops.detect_markers.
3. Tab 3: Review list, **Απενεργοποίηση/Ενεργοποίηση** → @pdf_ops Marker.keep.
4. Tab 2: **Δημιουργία PDF με Κουμπιά** → @pdf_ops.apply_markers.
5. Tab 4: **Κωδικός Βιβλίου** (e.g. AN01), **Bunny Base URL** (@config.BUNNY_BASE_URL), optional **Φάκελος MP3**.
6. Tab 4: **Έλεγχος MP3** → @validators.validate_missing_mp3 / @database.validate_mp3_files.
7. Tab 4: **Δημιουργία database.xlsx** → @database.build_database_xlsx (validators run first in @app._gen_db).

## Out of scope (do not add)

- Batch / multi-book.
- Thinkific or FlipBuilder API calls.
- Changing @pdf_ops marker detection or button placement.
