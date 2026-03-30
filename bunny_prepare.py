# -*- coding: utf-8 -*-
"""
Bunny.net chapter preparation — scan source_books, validate, copy to output_ready,
rewrite audio URLs to deterministic CDN paths. No upload.

CLI: python app.py prepare_bunny [--source DIR] [--output DIR] [--cdn-base URL]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import quote

from config import (
    BUNNY_BASE_URL,
    BUNNY_ROOT_FOLDER,
    OUTPUT_READY_ROOT,
    SOURCE_BOOKS_ROOT,
    is_production_book_slug,
)


# ─── URL rewriting ─────────────────────────────────────────────────────

# Match src/href pointing to audio mp3 (relative paths from chapter or html/)
_AUDIO_REF_RE = re.compile(
    r'(?P<attr>\b(?:src|href)\s*=\s*)'
    r'(?P<q>["\'])'
    r'(?P<path>(?:\.\./|\./)?audio/[^"\']+\.mp3)'
    r'(?P=q)',
    re.IGNORECASE,
)

def build_chapter_base_url(cdn_base: str, path_prefix: str, book_slug: str, chapter_slug: str) -> str:
    """https://host/books/book_slug/chapter_slug (no trailing slash)."""
    base = (cdn_base or "").strip().rstrip("/")
    pp = (path_prefix or "").strip().strip("/")
    bs = (book_slug or "").strip().strip("/")
    cs = (chapter_slug or "").strip().strip("/")
    return f"{base}/{quote(pp, safe='')}/{quote(bs, safe='')}/{quote(cs, safe='')}"


def build_audio_file_url(chapter_base_url: str, filename: str) -> str:
    """Full URL for one MP3 under .../audio/filename."""
    fn = (filename or "").strip()
    if not fn:
        return chapter_base_url + "/audio/"
    return f"{chapter_base_url}/audio/{quote(fn, safe='/')}"


def rewrite_html_audio_refs(html: str, chapter_base_url: str) -> Tuple[str, int]:
    """
    Replace relative audio/ and ../audio/ references with absolute Bunny URLs.
    Returns (new_html, replacement_count).
    """
    audio_base = f"{chapter_base_url.rstrip('/')}/audio"
    count = 0

    def sub1(m: re.Match) -> str:
        nonlocal count
        path = m.group("path")
        fname = Path(path).name
        url = f"{audio_base}/{quote(fname, safe='/')}"
        count += 1
        return f'{m.group("attr")}{m.group("q")}{url}{m.group("q")}'

    out = _AUDIO_REF_RE.sub(sub1, html)
    return out, count


# ─── Discovery & validation ───────────────────────────────────────────

_MP3_LEADING_DIGITS = re.compile(r"^(\d{3})\s", re.IGNORECASE)
_MP3_CODE_STYLE = re.compile(r"^[A-Za-z]{2,10}\d{2,4}-\d{3}\.mp3$", re.IGNORECASE)


def _list_mp3_files(audio_dir: Path) -> List[Path]:
    if not audio_dir.is_dir():
        return []
    return sorted(
        p for p in audio_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".mp3"
    )


def _list_html_files(html_dir: Path) -> List[Path]:
    if not html_dir.is_dir():
        return []
    return sorted(p for p in html_dir.iterdir() if p.is_file() and p.suffix.lower() == ".html")


def _check_mp3_naming(files: List[Path]) -> List[str]:
    """Return warnings for inconsistent naming."""
    warns: List[str] = []
    if not files:
        return warns
    styles = {"digits": 0, "code": 0, "other": 0}
    for p in files:
        name = p.name
        if _MP3_CODE_STYLE.match(name):
            styles["code"] += 1
        elif _MP3_LEADING_DIGITS.match(name):
            styles["digits"] += 1
        else:
            styles["other"] += 1
    non_zero = sum(1 for v in styles.values() if v > 0)
    if non_zero > 1:
        warns.append(
            f"Mixed MP3 naming styles (digits-prefix / CODE-NNN / other): {styles}"
        )
    return warns


@dataclass
class ChapterResult:
    book_slug: str
    chapter_slug: str
    book_name: str
    chapter_name: str
    local_chapter_path: str
    local_html_path: str
    local_audio_path: str
    output_chapter_path: str
    status: str  # READY | ERROR
    bunny_index_url: str
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    url_replacements: int = 0


def discover_chapters(source_root: Path) -> List[Tuple[str, str, Path]]:
    """
    Return list of (book_slug, chapter_slug, chapter_path).
    Expects: source_root/book_slug/chapter_slug/ with html/ and audio/.
    """
    out: List[Tuple[str, str, Path]] = []
    if not source_root.is_dir():
        return out
    for book_dir in sorted(source_root.iterdir()):
        if not book_dir.is_dir() or book_dir.name.startswith("."):
            continue
        book_slug = book_dir.name
        for ch_dir in sorted(book_dir.iterdir()):
            if not ch_dir.is_dir() or ch_dir.name.startswith("."):
                continue
            chapter_slug = ch_dir.name
            out.append((book_slug, chapter_slug, ch_dir))
    return out


def prepare_one_chapter(
    book_slug: str,
    chapter_slug: str,
    chapter_path: Path,
    output_root: Path,
    cdn_base: str,
    path_prefix: str,
) -> ChapterResult:
    """Validate, copy to output_ready, rewrite HTML. Returns ChapterResult."""
    html_dir = chapter_path / "html"
    audio_dir = chapter_path / "audio"
    local_chapter = str(chapter_path.resolve())
    issues: List[str] = []
    warnings: List[str] = []

    book_name = book_slug.replace("-", " ").title()
    chapter_name = chapter_slug.replace("_", " ").replace("-", " ")

    chapter_base = build_chapter_base_url(cdn_base, path_prefix, book_slug, chapter_slug)
    index_url = f"{chapter_base}/index.html"

    if not html_dir.is_dir():
        issues.append(f"Missing or not a directory: {html_dir}")
    if not audio_dir.is_dir():
        issues.append(f"Missing or not a directory: {audio_dir}")

    html_files = _list_html_files(html_dir) if html_dir.is_dir() else []
    mp3_files = _list_mp3_files(audio_dir) if audio_dir.is_dir() else []

    if html_dir.is_dir() and not html_files:
        issues.append("No .html files in html/")
    if audio_dir.is_dir() and not mp3_files:
        issues.append("No .mp3 files in audio/")

    warnings.extend(_check_mp3_naming(mp3_files))

    out_chapter = output_root / book_slug / chapter_slug
    status = "ERROR" if issues else "READY"

    if issues:
        return ChapterResult(
            book_slug=book_slug,
            chapter_slug=chapter_slug,
            book_name=book_name,
            chapter_name=chapter_name,
            local_chapter_path=local_chapter,
            local_html_path=str(html_dir.resolve()) if html_dir.is_dir() else str(html_dir),
            local_audio_path=str(audio_dir.resolve()) if audio_dir.is_dir() else str(audio_dir),
            output_chapter_path=str(out_chapter.resolve()),
            status="ERROR",
            bunny_index_url=index_url,
            issues=issues,
            warnings=warnings,
        )

    # Idempotent: replace entire chapter output tree
    if out_chapter.exists():
        shutil.rmtree(out_chapter)
    out_chapter.mkdir(parents=True)
    out_audio = out_chapter / "audio"
    out_audio.mkdir(parents=True)

    for mp3 in mp3_files:
        shutil.copy2(mp3, out_audio / mp3.name)

    # HTML: prefer index.html
    if (html_dir / "index.html").is_file():
        main_html = html_dir / "index.html"
        dest_index = out_chapter / "index.html"
        shutil.copy2(main_html, dest_index)
    elif html_files:
        shutil.copy2(html_files[0], out_chapter / "index.html")
        if len(html_files) > 1:
            warnings.append(
                f"Multiple HTML files; using {html_files[0].name} as index.html. Copy others manually if needed."
            )
        for extra in html_files[1:]:
            shutil.copy2(extra, out_chapter / extra.name)
    else:
        issues.append("No HTML to copy")
        return ChapterResult(
            book_slug=book_slug,
            chapter_slug=chapter_slug,
            book_name=book_name,
            chapter_name=chapter_name,
            local_chapter_path=local_chapter,
            local_html_path=str(html_dir.resolve()),
            local_audio_path=str(audio_dir.resolve()),
            output_chapter_path=str(out_chapter.resolve()),
            status="ERROR",
            bunny_index_url=index_url,
            issues=issues,
            warnings=warnings,
        )

    # Rewrite all html in output chapter root
    total_repl = 0
    for html_out in out_chapter.glob("*.html"):
        text = html_out.read_text(encoding="utf-8", errors="replace")
        new_text, n = rewrite_html_audio_refs(text, chapter_base)
        total_repl += n
        html_out.write_text(new_text, encoding="utf-8")

    if total_repl == 0:
        warnings.append(
            "No audio src/href patterns rewritten (expected ../audio/... or audio/... in HTML)."
        )

    return ChapterResult(
        book_slug=book_slug,
        chapter_slug=chapter_slug,
        book_name=book_name,
        chapter_name=chapter_name,
        local_chapter_path=local_chapter,
        local_html_path=str(html_dir.resolve()),
        local_audio_path=str(audio_dir.resolve()),
        output_chapter_path=str(out_chapter.resolve()),
        status=status,
        bunny_index_url=index_url,
        issues=issues,
        warnings=warnings,
        url_replacements=total_repl,
    )


def prepare_all(
    source_root: Path,
    output_root: Path,
    cdn_base: str,
    path_prefix: str,
    include_non_production: bool = False,
) -> List[ChapterResult]:
    """Scan source_root, prepare each chapter. Skips demo/example books unless include_non_production."""
    results: List[ChapterResult] = []
    chapters = discover_chapters(source_root)
    if not chapters:
        return results
    output_root.mkdir(parents=True, exist_ok=True)
    for book_slug, chapter_slug, chapter_path in chapters:
        if not include_non_production and not is_production_book_slug(book_slug):
            continue
        r = prepare_one_chapter(
            book_slug, chapter_slug, chapter_path, output_root, cdn_base, path_prefix
        )
        results.append(r)
    return results


def print_summary_table(results: List[ChapterResult]) -> None:
    """Print a clean terminal table."""
    if not results:
        print("\n  (No chapters found under source_books. See source_books/README.md)\n")
        return
    cols = [
        ("Book", 20),
        ("Chapter", 18),
        ("Status", 8),
        ("Output path", 72),
    ]
    header = " | ".join(h.ljust(w)[:w] for h, w in cols)
    print("\n" + "=" * len(header))
    print(header)
    print("-" * len(header))
    for r in results:
        row = [
            r.book_slug[:20].ljust(20),
            r.chapter_slug[:18].ljust(18),
            r.status[:8].ljust(8),
            r.output_chapter_path[:72].ljust(72),
        ]
        print(" | ".join(row))
    print("=" * len(header) + "\n")


def print_detailed_report(results: List[ChapterResult]) -> None:
    for r in results:
        print(f"\n--- {r.book_slug} / {r.chapter_slug} ---")
        print(f"  Status:       {r.status}")
        print(f"  Local:        {r.local_chapter_path}")
        print(f"  HTML:         {r.local_html_path}")
        print(f"  Audio:        {r.local_audio_path}")
        print(f"  Output:       {r.output_chapter_path}")
        print(f"  Bunny index:  {r.bunny_index_url}")
        print(f"  URL rewrites: {r.url_replacements}")
        if r.issues:
            print("  Issues:")
            for i in r.issues:
                print(f"    - {i}")
        if r.warnings:
            print("  Warnings:")
            for w in r.warnings:
                print(f"    - {w}")


def main_cli(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare book chapters for Bunny.net (no upload).",
    )
    parser.add_argument(
        "--source",
        default=SOURCE_BOOKS_ROOT,
        help=f"Root folder containing book_slug/chapter_slug/ (default: {SOURCE_BOOKS_ROOT})",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_READY_ROOT,
        help=f"Output folder for Bunny-ready files (default: {OUTPUT_READY_ROOT})",
    )
    parser.add_argument(
        "--cdn-base",
        default=BUNNY_BASE_URL,
        help="CDN base URL (no trailing path; default from config)",
    )
    parser.add_argument(
        "--path-prefix",
        default=BUNNY_ROOT_FOLDER,
        help=f"Path segment after host (default: {BUNNY_ROOT_FOLDER})",
    )
    parser.add_argument(
        "--include-non-production",
        action="store_true",
        help="Include example_/demo_/test_/sample_ books and known demo slugs",
    )
    args = parser.parse_args(argv)

    source_root = Path(args.source).resolve()
    output_root = Path(args.output).resolve()
    cdn_base = (args.cdn_base or "").strip()
    path_prefix = (args.path_prefix or BUNNY_ROOT_FOLDER).strip()

    print("\nTofanari Main Tool - Bunny prepare (chapter-level)")
    print(f"  Source:  {source_root}")
    print(f"  Output:  {output_root}")
    print(f"  CDN base: {cdn_base}")
    print(f"  Prefix:   /{path_prefix}/{{book_slug}}/{{chapter_slug}}/")

    if not source_root.is_dir():
        print(f"\nERROR: Source root does not exist: {source_root}", file=sys.stderr)
        print("Create it and add: source_books/<book_slug>/<chapter_slug>/html/ and audio/", file=sys.stderr)
        return 2

    results = prepare_all(
        source_root,
        output_root,
        cdn_base,
        path_prefix,
        include_non_production=args.include_non_production,
    )
    print_detailed_report(results)
    print_summary_table(results)

    ready = sum(1 for r in results if r.status == "READY")
    err = sum(1 for r in results if r.status == "ERROR")
    print(f"Summary: {ready} READY, {err} ERROR, {len(results)} chapter(s) total.\n")

    if not results:
        all_ch = discover_chapters(source_root)
        if all_ch and not args.include_non_production:
            print(
                "Hint: Only production book folders are prepared by default. "
                "Use --include-non-production to prepare demo/example books.\n",
                file=sys.stderr,
            )
        return 1
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main_cli())
