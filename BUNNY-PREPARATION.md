# Bunny.net Chapter Preparation Guide

This guide covers the **Bunny preparation stage** for the ToFanari professional publishing workflow. Chapters are validated individually before upload; merging into complete books happens later.

---

## Recommended Bunny Folder Structure

```
{BUNNY_ROOT_FOLDER}/{book_slug}/{chapter_code}/
```

**Example:**
```
books/
  anastasimatarion/
    AN01/
      AN01-001.mp3
      AN01-002.mp3
      ...
    AN02/
      AN02-001.mp3
      ...
  minaio-ian/
    MI01/
      MI01-001.mp3
      ...
```

**URL pattern:**
```
{base_cdn_url}/{root_folder}/{book_slug}/{chapter_code}/{CHAPTERCODE-NNN.mp3}
```
Example: `https://fanari.b-cdn.net/books/anastasimatarion/AN01/AN01-001.mp3`

---

## Naming Conventions

| Item | Rule | Example |
|------|------|---------|
| **Book slug** | Lowercase, hyphen-separated, no spaces | `anastasimatarion`, `minaio-ian` |
| **Chapter code** | Uppercase alphanumeric, 2–4 chars | `AN01`, `MI03` |
| **MP3 filename** | `CHAPTERCODE-NNN.mp3` | `AN01-001.mp3` |
| **Source MP3** | `NNN Title.mp3` (leading 3 digits) | `001 Κύριε ἐκέκραξα.mp3` |
| **Bunny folder** | `root/book_slug/chapter_code/` | `books/anastasimatarion/AN01/` |

---

## Chapters Manifest

Create a CSV or XLSX file listing chapters to validate and prepare.

**Required columns:**
- `book_slug` — Bunny folder name for the book
- `chapter_code` — Chapter identifier (e.g. AN01)
- `local_work_folder` — Path to folder containing `database.xlsx` for this chapter
- `local_mp3_folder` — Path to folder containing MP3 files for this chapter

**Optional columns (for report display):**
- `book_title` — Human-readable book name
- `chapter_name` — Human-readable chapter name

**Example CSV:**
```csv
book_slug,chapter_code,local_work_folder,local_mp3_folder,book_title,chapter_name
anastasimatarion,AN01,C:\work\AN01,C:\work\AN01\mp3,Αναστασιματάριο,Κύριε ἐκέκραξα
anastasimatarion,AN02,C:\work\AN02,C:\work\AN02\mp3,Αναστασιματάριο,Ψαλμοί
```

---

## How to Run Bunny Preparation

1. **Create manifest template** (first time):
   - Tab 7 → "Create Manifest Template"
   - Save as `chapters_manifest.csv`
   - Edit paths and add more rows

2. **Set Bunny config** (Tab 7):
   - Base CDN URL: `https://your-zone.b-cdn.net`
   - Root remote folder: `books` (default)

3. **Run preparation**:
   - Tab 7 → "Load Manifest & Run Preparation"
   - Select your `chapters_manifest.csv`
   - Review the report in the preview area

4. **Interpret report**:
   - `READY` — Chapter passes validation; safe to upload
   - `NOT_READY` — Fix errors before upload

---

## Validation Checks (Per Chapter)

| Check | Description |
|-------|-------------|
| Work folder exists | `local_work_folder` is a valid directory |
| database.xlsx | Present and readable in work folder |
| Chapter code | Extracted from MP3 Code column; consistent with manifest |
| MP3 folder exists | `local_mp3_folder` is a valid directory |
| MP3 numbering | Source files follow `001`, `002`, ... (no gaps) |
| Row vs MP3 count | Hymn row count matches MP3 file count |
| Bunny config | Base URL valid; book slug has no spaces |

---

## Database.xlsx and Bunny URLs

The `database.xlsx` built in Tab 4 uses a simpler URL pattern: `{base}/{chapter_code}/{CHAPTERCODE-NNN.mp3}` (e.g. `base/AN01/AN01-001.mp3`). The Chapter Preparation report uses the nested structure `{base}/{root}/{book_slug}/{chapter_code}/` for clearer organization. Align your Bunny Storage structure with the report’s “Bunny target” paths. If you use the nested structure, you may need to update the Bunny URL column in `database.xlsx` when generating it, or ensure your FlipBuilder/Thinkific setup uses the correct base path.

---

## Next Steps After Preparation

1. **Upload** — Use Bunny Storage API or Pull Zone to upload each chapter's MP3 folder to `{root}/{book_slug}/{chapter_code}/`
2. **Verify** — Test URLs after upload
3. **Merge** — (Later) Merge validated chapters into a complete book for FlipBuilder
4. **FlipBuilder** — Import merged book, add flip effect and audio player
5. **Thinkific** — Publish the complete book

---

## Files Touched by This Stage

- `bunny_preparation.py` — Chapter validation and report
- `config.py` — `BUNNY_ROOT_FOLDER`
- `app.py` — Tab 7 "Chapter Preparation" UI
- `BUNNY-PREPARATION.md` — This guide
