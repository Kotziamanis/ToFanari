# Bunny.net Storage upload

Upload prepared chapter folders to **Bunny Storage** so public URLs match your **Pull Zone**.

## Gated workflow (default)

`python app.py upload_bunny` runs a **discovery → validation → selection → confirmation → prepare → upload** pipeline. It does **not** upload demo/example/test/sample books unless you explicitly select them in the GUI/terminal step.

1. **Scan** `source_books/` for every chapter folder.
2. **Validate** each chapter (HTML, `audio/`, MP3s, naming, HTML→audio links, Bunny target paths). Failed items are **NOT READY** and cannot be uploaded.
3. **Select** which READY chapters to upload (one book, many books, or “all READY production”).
4. **Confirm** a summary (books, chapters, audio status, ready/not ready, Bunny paths).
5. **Clear** `output_ready/` (except `README.md`), **prepare only** the selected chapters, then **upload** only those files.

Workflow report (validation + eligibility):

- Default: `bunny_workflow_report.json` in the project root (gitignored)

Upload report (per-file URLs):

- Default: `upload_report.json`

### Dry run (validation + summary only, no GUI/credentials)

```bash
cd c:\Users\User\ToFanari_v4
python app.py upload_bunny --dry-run
```

### Legacy: upload everything already in `output_ready/`

Skips discovery/validation/selection (use only if you prepared manually):

```bash
python app.py upload_bunny --legacy-upload-all
```

### Options

```text
--source DIR           Book root (default: source_books)
--output DIR           Prepared output / upload source (default: output_ready)
--cdn-base URL         CDN base for prepared HTML (default from config)
--prefix NAME          Remote prefix (default: books)
--report FILE          upload_report.json path
--workflow-report FILE bunny_workflow_report.json path
--dry-run              Validate and summarize only
--legacy-upload-all    Old behaviour: upload all of --output
-v, --verbose          Debug logging
```

## Prerequisites

**Production prepare** (excludes demo/example folders by default):

```bash
python app.py prepare_bunny
```

**Include non-production books** in prepare:

```bash
python app.py prepare_bunny --include-non-production
```

For **upload**, non-production READY chapters appear in the selection UI **unchecked**; you can tick them explicitly.

## Credentials (when not `--dry-run` and not `--legacy-upload-all`)

A credential dialog opens (or terminal prompt if no GUI). Enter:

- **Storage Zone name** — hostname segment from Bunny
- **API Key** — Storage Zone password (FTP & API Access tab)
- **Pull Zone URL** — e.g. `https://your-pull-zone.b-cdn.net`
- **Storage host** — optional, default `storage.bunnycdn.com`

**Buttons:** Test connection · Save credentials (`settings/bunny_credentials.json`, gitignored) · Continue upload · Cancel

## Remote layout

```text
/{prefix}/{book_slug}/{chapter_slug}/index.html
/{prefix}/{book_slug}/{chapter_slug}/audio/*.mp3
```

## Behaviour

- **Overwrite:** PUT replaces existing objects at the same path.
- **Retries:** failed uploads retry with backoff.
- **Safety:** NOT READY chapters are disabled in the GUI and blocked from upload; failed items show exact reasons in `bunny_workflow_report.json`.
