# Source books layout (Bunny prepare)

Place each book under `source_books/<book_slug>/` with one folder per chapter.

## Required structure per chapter

```
source_books/
  <book_slug>/
    <chapter_slug>/
      html/          ← at least one .html (prefer index.html)
      audio/         ← .mp3 files for this chapter
```

## Example

```
source_books/
  anastasimatarion/
    chapter_01/
      html/
        index.html
      audio/
        001 Title.mp3
        002 Another.mp3
    chapter_02/
      html/
        index.html
      audio/
        001 ...
```

## HTML audio references

Use relative paths so they can be rewritten to your CDN:

- `../audio/filename.mp3` (from `html/index.html`)
- `audio/filename.mp3` (if referenced from chapter root after copy)

## Run preparation

From the project root:

```bash
python app.py prepare_bunny
```

Output goes to `output_ready/<book_slug>/<chapter_slug>/` with `index.html` and `audio/`.
