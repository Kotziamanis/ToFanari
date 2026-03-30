# Tofanari Main Tool → Single-Book Production Tool — Implementation Plan

## STEP 1 — Implementation plan

### Scope (what we do)
- **Single book only**: one PDF, one Book Code, one MP3 folder. No batch, no multi-book, no Thinkific/FlipBuilder APIs.
- **Goal**: Perfect the workflow for one book; keep assets and database ready for Bunny, FlipBuilder, and future Thinkific.

### Architecture (unchanged)
- **config.py** — Constants, UI colors, button geometry, **Bunny settings** (base URL, use book subfolder).
- **pdf_ops.py** — **No changes.** Marker detection, button placement, PDF export stay as-is.
- **database.py** — Production Excel (new columns), Bunny URL with folder-per-book, MP3 naming BOOKCODE-NNN.mp3.
- **validators.py** — **New.** Validation helpers: empty book code, duplicate IDs/positions, invalid pages, missing MP3s.
- **app.py** — UI: Book Code, Bunny URL, **MP3 folder** (optional), **Validate MP3** button; call validators before export.

### Data flow
1. User selects PDF and (optionally) MP3 folder.
2. Detect markers → review → generate PDF with buttons (unchanged).
3. User sets Book Code (required for production export).
4. Export database: one row per marker (ID 001,002,…, Page, X, Y, Width, Height, MP3_File, MP3_URL, Active, First_Words, Notes).
5. Bunny URL = `{base}/{BOOKCODE}/{BOOKCODE}-{NNN}.mp3`.
6. Validate MP3: check selected MP3 folder for expected BOOKCODE-NNN.mp3 files (current book only).

### Excel export (production-ready)
- **ID**: 001, 002, 003 (from marker order).
- **Page, X, Y**: from marker (X default from config).
- **Width, Height**: from config (BTN_W, BTN_H).
- **MP3_File**: BOOKCODE-NNN.mp3.
- **MP3_URL**: `BUNNY_BASE_URL/BOOKCODE/BOOKCODE-NNN.mp3` when USE_BOOK_SUBFOLDER.
- **Active**: 1 (kept) or 0 (disabled).
- **First_Words, Notes**: empty for now.
- Export **all** markers (kept + disabled) so production has full list; Active distinguishes.

### Validation (single-book)
- Empty Book Code → block export and warn.
- Duplicate (page, y) → warn.
- Invalid page numbers → warn.
- Missing MP3 files in selected MP3 folder → warn (list missing).
- No batch validation; only current book’s expected files.

---

## STEP 2 — Code changes by file

| File | Changes |
|------|--------|
| **config.py** | Add `BUNNY_BASE_URL`, `USE_BOOK_SUBFOLDER`; set `DEFAULT_BUNNY_BASE_URL` from `BUNNY_BASE_URL`; bump `APP_VERSION` in config.py (e.g. v1.1.0). |
| **database.py** | New production headers and row layout; `build_mp3_url(base, code, n)` with folder-per-book; `build_database_xlsx` writes new columns (all markers, Active 1/0); `validate_mp3_files(mp3_folder, markers, code)` — use explicit MP3 folder. |
| **validators.py** | **New file.** `validate_empty_book_code(code)`, `validate_duplicate_positions(markers)`, `validate_page_numbers(markers)`, `validate_missing_mp3(mp3_folder, markers, code)` (delegate to database or reimplement). |
| **app.py** | Add `mp3_fold` StringVar; Tab 4: Book Code, Bunny URL, **MP3 folder** + Browse, **Validate MP3** button; before export run validators and show errors; after export run MP3 validation if folder set; fix module-level `if __name__`. |
| **pdf_ops.py** | No changes. |

---

## STEP 6 — User workflow (single book, start to finish)

1. **Select PDF** (Tab 1): Choose workbook folder and the PDF that contains ■ markers.
2. **Detect markers** (Tab 2): Run “Εντοπισμός Markers” → list of ■ positions.
3. **Review markers** (Tab 3): Disable any wrong markers (they get Active=0 in export).
4. **Generate PDF** (Tab 2): “Δημιουργία PDF με Κουμπιά” → PDF with numbered buttons, ■ hidden.
5. **Set book data** (Tab 4): Enter **Book Code** (e.g. AN01), **Bunny Base URL** (e.g. https://fanari.b-cdn.net). Optionally set **MP3 folder** where AN01-001.mp3, AN01-002.mp3… live.
6. **Validate MP3** (Tab 4): Click “Validate MP3” to check that all expected files exist in the MP3 folder; missing files are listed.
7. **Export database** (Tab 4): “Δημιουργία database.xlsx” → production Excel with ID, Page, X, Y, Width, Height, MP3_File, MP3_URL, Active, First_Words, Notes. If any validation fails (e.g. empty Book Code), show error and do not overwrite.
8. **Use outputs**: Use the PDF in FlipBuilder; use database for Bunny upload and future Thinkific linking. No integration implemented in app — only asset preparation.
