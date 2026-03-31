# ToFanari — Testing Guide (Pilot: MIKP)

## 1. How to Build the EXE

### Step-by-step

1. Open a terminal in the project folder (`ToFanari_v4`).
2. Set the version in `config.py` if needed (edit `APP_VERSION`, e.g. `"v1.5.0"`).
3. Run: `python build_new_version.py`
4. The script will:
   - Read `APP_VERSION` from `config.py`
   - Install dependencies (pymupdf, openpyxl, PyInstaller)
   - Clean old build folders
   - Build the executable with PyInstaller
   - Print the version being built

### Where the EXE is located

- **Main output:** `dist/ToFanari.exe`
- **Versioned build:** `builds/ToFanari_{version}/tofanari.exe` (e.g. `builds/ToFanari_v1.5.0/tofanari.exe`)

Run: `dist\ToFanari.exe` (or `.\dist\ToFanari.exe` on Windows).

---

## 2. How to Define Books in Parameters

Books and collections are stored in `settings/parameters.json`.

### Default structure

- **Collections:** `collection_code`, `title`, `display_order`
- **Books:** `code`, `title`, `collection`, `expected_chapters`, `active`, `book_slug`, `chapters`

### Pilot books (predefined)

| Book Code | Title                         | Collection   | Expected Chapters |
|-----------|-------------------------------|--------------|-------------------|
| MIKP      | Μικρός Παρακλητικός Κανών     | PARAKLITIKOI | 1                 |
| MEPK      | Μέγας Παρακλητικός Κανών      | PARAKLITIKOI | 1                 |

Collection `PARAKLITIKOI` → "Παρακλητικοί".

### Creating parameters.json

- If the file does not exist, it is created on first app launch with the default (including MINAIO + PARAKLITIKOI).
- To add pilot books to an existing file, load Parameters and they will be added automatically if missing.
- Edit `parameters.json` manually, or use “Load Parameters” and “Add Book to Registry” for Excel-based workflows.

---

## 3. Ready PDF Workflow (Correct Usage)

### Prerequisites

1. Load Parameters (Tab 0).
2. Confirm that MIKP (and any other books) appear in the book list.

### Steps

1. **Tab 6 (Έλεγχος Βάσης):** Click “Επιλογή Έτοιμου PDF”.
2. Select a PDF that has markers (■) and has already been prepared.
3. If validation passes: “Σύνδεση με βιβλίο” is enabled.
4. Click “Σύνδεση με βιβλίο”.
5. Choose **book** from the dropdown (no manual typing).
6. Choose **chapter** from the dropdown for that book.
7. Click OK to register.

### Important rules

- Catalog must be loaded before association; otherwise you see: “Φορτώστε πρώτα το Parameters (Tab 0)”.
- Selection must be from the predefined catalog (dropdown only).
- Manual book codes are not allowed.

---

## 4. Interpreting Validation Results

### PDF validation (when picking Ready PDF)

- **Markers found:** Number of markers (■) in the PDF.
- **Marker sequence:** OK or ERROR (duplicates, invalid pages).
- **RESULT:** PASS (green) or FAIL (red).

### MP3 / Marker validation (when MP3 folder is set)

- **MP3 count:** Number of MP3 files found.
- **Matched markers vs audio:** How many markers have matching audio.
- **MP3 ↔ Markers:** OK or MISMATCH.

### Database validation (“Έλεγχος Βάσης”)

- **STATUS:** DATABASE OK, OK WITH WARNINGS, or NOT READY.
- Green = proceed; yellow = review; red = fix errors first.

---

## 5. Confirming a Book is COMPLETE

1. **Tab 0 (Parameters):** Load Parameters.
2. Select the book (e.g. MIKP) from the list.
3. Click “Compare imported vs expected”.
4. Check the report:
   - **Expected chapters:** MIKP (for single-chapter book).
   - **Imported chapters:** MIKP (after successful import).
   - **Missing chapters:** (none).
   - **Status:** COMPLETE.

5. **Merge button:** When status is COMPLETE, the “Merge (when complete)” button becomes enabled. It is disabled when there are missing, duplicate, or invalid chapters.

### For MIKP (expected 1 chapter)

- After importing the one chapter, the report should show: **Status: COMPLETE (1/1 imported)**.
- Merge is allowed when all expected chapters are imported and validated.

---

## 6. Debug Logging

Imports are logged to `settings/tofanari.log`:

```
[2025-03-09 14:30:00] IMPORT | book=mikp | chapter=MIKP | markers=42 | mp3_matched=42
```

Use this to check:
- Selected book and chapter.
- Number of markers.
- Number of MP3 files matched.

---

## 7. Merge Safety

Merge is only allowed when:

- All expected chapters are imported.
- There are no duplicate chapters.
- There are no invalid entries.

Otherwise the Merge button stays disabled and shows the reason (e.g. “Merge blocked: missing chapters”).
