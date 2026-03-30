# -*- coding: utf-8 -*-
"""
Bunny professional workflow: discover books, validate chapters, select, prepare, upload.
Excludes demo/example/test/sample books from default upload selection.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import (
    BUNNY_BASE_URL,
    BUNNY_ROOT_FOLDER,
    OUTPUT_READY_ROOT,
    SOURCE_BOOKS_ROOT,
    is_production_book_slug,
)

from bunny_prepare import (
    build_chapter_base_url,
    discover_chapters,
    prepare_one_chapter,
    _list_html_files,
    _list_mp3_files,
    _check_mp3_naming,
    _AUDIO_REF_RE,
)


# ---------------------------------------------------------------------------
# Chapter validation (no file copy)
# ---------------------------------------------------------------------------


def _missing_audio_refs(html_dir: Path, audio_dir: Path) -> List[str]:
    """HTML references to ../audio/X.mp3 or audio/X.mp3 must exist on disk."""
    issues: List[str] = []
    if not html_dir.is_dir() or not audio_dir.is_dir():
        return issues
    for html in html_dir.glob("*.html"):
        try:
            text = html.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            issues.append(f"Cannot read {html.name}: {e}")
            continue
        for m in _AUDIO_REF_RE.finditer(text):
            fname = Path(m.group("path")).name
            if not (audio_dir / fname).is_file():
                issues.append(f"{html.name} references missing audio file: {fname}")
    return issues


def analyze_chapter(
    book_slug: str,
    chapter_slug: str,
    chapter_path: Path,
    cdn_base: str,
    path_prefix: str,
) -> "ChapterWorkflowRecord":
    """Validate chapter layout; no prepare/copy."""
    html_dir = chapter_path / "html"
    audio_dir = chapter_path / "audio"
    issues: List[str] = []
    warnings: List[str] = []

    chapter_base = build_chapter_base_url(cdn_base, path_prefix, book_slug, chapter_slug)
    bunny_index_url = f"{chapter_base}/index.html"
    bunny_target = f"{path_prefix.strip().strip('/')}/{book_slug}/{chapter_slug}/"

    html_status = "MISSING"
    audio_status = "MISSING"

    if not html_dir.is_dir():
        issues.append(f"Missing html/ folder: {html_dir}")
    else:
        html_status = "OK" if _list_html_files(html_dir) else "EMPTY"

    if not audio_dir.is_dir():
        issues.append(f"Missing audio/ folder: {audio_dir}")
    else:
        mp3s = _list_mp3_files(audio_dir)
        audio_status = "OK" if mp3s else "EMPTY"

    html_files = _list_html_files(html_dir) if html_dir.is_dir() else []
    mp3_files = _list_mp3_files(audio_dir) if audio_dir.is_dir() else []

    if html_dir.is_dir() and not html_files:
        issues.append("No .html files in html/")
    if audio_dir.is_dir() and not mp3_files:
        issues.append("No .mp3 files in audio/")

    warnings.extend(_check_mp3_naming(mp3_files))
    issues.extend(_missing_audio_refs(html_dir, audio_dir))

    validation_status = "NOT_READY" if issues else "READY"
    prod = is_production_book_slug(book_slug)
    # Eligible for default "upload all" = READY + production
    upload_eligible_default = validation_status == "READY" and prod

    return ChapterWorkflowRecord(
        book_slug=book_slug,
        chapter_slug=chapter_slug,
        chapter_path=str(chapter_path.resolve()),
        is_production_book=prod,
        html_status=html_status,
        audio_status=audio_status,
        validation_status=validation_status,
        upload_eligible_default=upload_eligible_default,
        bunny_target_prefix=bunny_target,
        bunny_index_url=bunny_index_url,
        issues=list(issues),
        warnings=list(warnings),
        uploaded_url=None,
    )


@dataclass
class ChapterWorkflowRecord:
    book_slug: str
    chapter_slug: str
    chapter_path: str
    is_production_book: bool
    html_status: str
    audio_status: str
    validation_status: str  # READY | NOT_READY
    upload_eligible_default: bool
    bunny_target_prefix: str
    bunny_index_url: str
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    uploaded_url: Optional[str] = None

    def to_report_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["upload_eligible_for_auto_select"] = self.upload_eligible_default
        d["selection_allowed"] = self.validation_status == "READY"
        return d


def discover_and_validate(
    source_root: Path,
    cdn_base: str = BUNNY_BASE_URL,
    path_prefix: str = BUNNY_ROOT_FOLDER,
) -> List[ChapterWorkflowRecord]:
    """Scan source_books and validate every chapter."""
    out: List[ChapterWorkflowRecord] = []
    for book_slug, chapter_slug, chapter_path in discover_chapters(source_root):
        out.append(
            analyze_chapter(book_slug, chapter_slug, chapter_path, cdn_base, path_prefix)
        )
    return out


def clear_output_ready_for_upload(output_root: Path) -> None:
    """Remove prepared content; keep README.md if present."""
    if not output_root.is_dir():
        output_root.mkdir(parents=True, exist_ok=True)
        return
    for child in list(output_root.iterdir()):
        if child.name.lower() == "readme.md":
            continue
        try:
            if child.is_dir():
                shutil.rmtree(child)
            elif child.is_file():
                child.unlink()
        except OSError:
            pass


def prepare_selected_chapters(
    selections: List[Tuple[str, str]],
    source_root: Path,
    output_root: Path,
    cdn_base: str,
    path_prefix: str,
) -> List[Any]:
    """Prepare only selected (book_slug, chapter_slug). Returns ChapterResult list."""
    from bunny_prepare import ChapterResult

    sel_set = set(selections)
    results: List[ChapterResult] = []
    for book_slug, chapter_slug, chapter_path in discover_chapters(source_root):
        if (book_slug, chapter_slug) not in sel_set:
            continue
        r = prepare_one_chapter(
            book_slug, chapter_slug, chapter_path, output_root, cdn_base, path_prefix
        )
        results.append(r)
    return results


def write_workflow_report(
    records: List[ChapterWorkflowRecord],
    path: Path,
    selected: Optional[List[Tuple[str, str]]] = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(Path(SOURCE_BOOKS_ROOT).resolve()),
        "chapters": [r.to_report_dict() for r in records],
        "selected_for_upload": [f"{a}/{b}" for a, b in (selected or [])],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _try_tk() -> bool:
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.destroy()
        return True
    except Exception:
        return False


def show_selection_dialog(
    records: List[ChapterWorkflowRecord],
) -> Optional[List[Tuple[str, str]]]:
    """
    GUI: select chapters to upload. NOT_READY cannot be selected.
    Returns list of (book_slug, chapter_slug) or None if cancelled.
    """
    import tkinter as tk
    from tkinter import ttk, messagebox

    vars_by_key: Dict[Tuple[str, str], tk.BooleanVar] = {}

    root = tk.Tk()
    root.title("Bunny upload - Select chapters")
    root.geometry("780x520")

    main = ttk.Frame(root, padding=12)
    main.pack(fill=tk.BOTH, expand=True)

    ttk.Label(
        main,
        text="Validated chapters (only READY can be uploaded). Demo/example books are unchecked by default.",
        wraplength=720,
    ).pack(anchor=tk.W)

    canvas = tk.Canvas(main, highlightthickness=0)
    sb = ttk.Scrollbar(main, orient=tk.VERTICAL, command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor=tk.NW)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    ttk.Label(inner, text="Upload?", font=("", 9, "bold")).grid(row=0, column=0, padx=4, pady=4)
    ttk.Label(inner, text="Book / Chapter", font=("", 9, "bold")).grid(row=0, column=1, padx=4, pady=4)
    ttk.Label(inner, text="Status", font=("", 9, "bold")).grid(row=0, column=2, padx=4, pady=4)
    ttk.Label(inner, text="Type", font=("", 9, "bold")).grid(row=0, column=3, padx=4, pady=4)

    for i, r in enumerate(records, start=1):
        key = (r.book_slug, r.chapter_slug)
        can_select = r.validation_status == "READY"
        v = tk.BooleanVar(value=can_select and r.upload_eligible_default)
        vars_by_key[key] = v
        cb = ttk.Checkbutton(inner, variable=v)
        cb.state(["!alternate"])
        if not can_select:
            cb.state(["disabled"])
        cb.grid(row=i, column=0, padx=4, pady=2)

        ttk.Label(inner, text=f"{r.book_slug} / {r.chapter_slug}").grid(row=i, column=1, sticky=tk.W, padx=4)
        st = r.validation_status
        ttk.Label(inner, text=st, foreground=("green" if st == "READY" else "red")).grid(
            row=i, column=2, padx=4
        )
        typ = "production" if r.is_production_book else "non-production (demo)"
        ttk.Label(inner, text=typ).grid(row=i, column=3, sticky=tk.W, padx=4)

    btn_row = ttk.Frame(main)
    btn_row.pack(fill=tk.X, pady=(10, 0))

    def select_ready_prod():
        for r in records:
            key = (r.book_slug, r.chapter_slug)
            v = vars_by_key[key]
            if r.validation_status == "READY" and r.upload_eligible_default:
                v.set(True)
            elif r.validation_status == "READY":
                v.set(False)
            # NOT_READY stays disabled

    def clear_all():
        for r in records:
            key = (r.book_slug, r.chapter_slug)
            if r.validation_status == "READY":
                vars_by_key[key].set(False)

    result: Optional[List[Tuple[str, str]]] = None

    def on_continue():
        nonlocal result
        picked: List[Tuple[str, str]] = []
        for r in records:
            key = (r.book_slug, r.chapter_slug)
            if r.validation_status == "READY" and vars_by_key[key].get():
                picked.append(key)
        if not picked:
            messagebox.showwarning("No selection", "Select at least one READY chapter, or cancel.")
            return
        lines = [
            "Confirm upload",
            "",
            f"Chapters to upload: {len(picked)}",
            "",
        ]
        for b, c in picked:
            lines.append(f"  - {b} / {c}")
        lines.append("")
        lines.append("output_ready will be cleared except README, then only these chapters will be prepared and uploaded.")
        if not messagebox.askyesno("Confirm upload", "\n".join(lines)):
            return
        result = picked
        root.destroy()

    def on_cancel():
        root.destroy()

    ttk.Button(btn_row, text="Select all READY production", command=select_ready_prod).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_row, text="Clear selection", command=clear_all).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_row, text="Continue to upload...", command=on_continue).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_row, text="Cancel", command=on_cancel).pack(side=tk.LEFT)

    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.mainloop()
    return result


def terminal_selection(records: List[ChapterWorkflowRecord]) -> Optional[List[Tuple[str, str]]]:
    """Fallback: number selection or 'all production ready'."""
    print("\n--- Chapter selection (terminal) ---\n")
    ready = [r for r in records if r.validation_status == "READY"]
    if not ready:
        print("No READY chapters. Fix validation errors first.")
        return None
    for i, r in enumerate(records, 1):
        tag = "[READY]" if r.validation_status == "READY" else "[NOT_READY]"
        prod = "prod" if r.is_production_book else "demo"
        print(f"  {i}. {tag} [{prod}] {r.book_slug} / {r.chapter_slug}")
        if r.issues:
            print(f"      Issues: {r.issues}")
    print("\nCommands:")
    print("  a = all READY production books (default safe)")
    print("  n = comma-separated numbers (e.g. 1,3)")
    print("  q = quit")
    choice = input("\nYour choice [a]: ").strip().lower() or "a"
    if choice == "q":
        return None
    picked: List[Tuple[str, str]] = []
    if choice == "a":
        for r in records:
            if r.validation_status == "READY" and r.upload_eligible_default:
                picked.append((r.book_slug, r.chapter_slug))
    else:
        try:
            nums = {int(x.strip()) for x in choice.split(",") if x.strip()}
        except ValueError:
            print("Invalid input.")
            return None
        for n in nums:
            if 1 <= n <= len(records):
                r = records[n - 1]
                if r.validation_status != "READY":
                    print(f"Chapter {n} is NOT_READY; skipped.")
                    continue
                picked.append((r.book_slug, r.chapter_slug))
    if not picked:
        print("Nothing selected.")
        return None
    print("\nSelected:", picked)
    c = input("Type YES to confirm upload: ").strip()
    if c != "YES":
        return None
    return picked


def run_gated_upload_workflow(
    source_root: Path,
    output_root: Path,
    report_path: Path,
    workflow_report_path: Path,
    cdn_base: str,
    path_prefix: str,
    dry_run: bool,
    verbose: bool = False,
) -> int:
    """Full gate: validate -> select -> confirm -> prepare selected -> credentials -> upload."""
    from bunny_upload import run_upload, _setup_logging
    from bunny_credentials import get_credentials_for_upload
    import logging

    _setup_logging(verbose)
    log = logging.getLogger("bunny_upload")

    if not source_root.is_dir():
        print(f"ERROR: Source not found: {source_root}", file=sys.stderr)
        return 2

    print("\nTofanari Main Tool - Bunny upload workflow")
    print(f"  Scanning: {source_root}")
    records = discover_and_validate(source_root, cdn_base, path_prefix)
    write_workflow_report(records, workflow_report_path)
    print(f"  Workflow report: {workflow_report_path}")

    if not records:
        print("ERROR: No chapters found under source_books.", file=sys.stderr)
        return 1

    # Print validation summary
    print("\n--- Validation summary ---")
    for r in records:
        prod = "production" if r.is_production_book else "NON-PRODUCTION"
        print(f"  {r.book_slug}/{r.chapter_slug}: {r.validation_status} | HTML={r.html_status} Audio={r.audio_status} | {prod}")
        for issue in r.issues:
            print(f"    ! {issue}")
        for w in r.warnings:
            print(f"    ~ {w}")

    not_ready = [r for r in records if r.validation_status == "NOT_READY"]
    if not_ready:
        print(f"\n  {len(not_ready)} chapter(s) NOT_READY (blocked from upload until fixed).")

    if dry_run:
        selected = []
        for r in records:
            if r.validation_status == "READY" and r.upload_eligible_default:
                selected.append((r.book_slug, r.chapter_slug))
        print(f"\n[DRY-RUN] Would default-select {len(selected)} production READY chapter(s).")
        print("  Skipping prepare, credentials, and upload.")
        return 0

    if _try_tk():
        selected = show_selection_dialog(records)
    else:
        selected = terminal_selection(records)

    if selected is None:
        print("Upload cancelled.")
        return 1

    write_workflow_report(records, workflow_report_path, selected=selected)

    # Prepare only selected; clear output_ready first
    print("\nPreparing selected chapters to output_ready...")
    clear_output_ready_for_upload(output_root)
    prep_results = prepare_selected_chapters(
        selected, source_root, output_root, cdn_base, path_prefix
    )
    failed_prep = [p for p in prep_results if p.status == "ERROR"]
    if failed_prep:
        print("ERROR: Prepare failed for:", file=sys.stderr)
        for p in failed_prep:
            print(f"  {p.book_slug}/{p.chapter_slug}: {p.issues}", file=sys.stderr)
        return 1

    creds = get_credentials_for_upload()
    if creds is None:
        print("Upload cancelled (credentials).")
        return 1

    log.info("Credentials loaded. Starting upload (selected chapters only).")
    log.info("Upload started.")
    code = run_upload(output_root, path_prefix, report_path, dry_run=False, credentials=creds)
    if code == 0:
        log.info("Upload completed successfully.")
    else:
        log.error("Upload finished with errors.")
    return code


def main_workflow_cli(argv: Optional[List[str]] = None) -> int:
    """Entry for app.py upload_bunny."""
    import argparse

    parser = argparse.ArgumentParser(description="Bunny gated upload workflow.")
    parser.add_argument("--source", default=SOURCE_BOOKS_ROOT)
    parser.add_argument("--output", default=OUTPUT_READY_ROOT)
    parser.add_argument("--cdn-base", default=BUNNY_BASE_URL)
    parser.add_argument("--prefix", default=BUNNY_ROOT_FOLDER)
    parser.add_argument("--report", default="upload_report.json")
    parser.add_argument("--workflow-report", default="bunny_workflow_report.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report only; no selection UI upload",
    )
    parser.add_argument(
        "--legacy-upload-all",
        action="store_true",
        help="Skip gate: upload entire output_ready without validation/selection (not recommended)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    report = Path(args.report).resolve()
    wf_report = Path(args.workflow_report).resolve()

    if args.legacy_upload_all:
        from bunny_upload import main_cli as upload_main

        raw = argv if argv is not None else __import__("sys").argv[2:]
        rest = [x for x in raw if x != "--legacy-upload-all"]
        return upload_main(rest)

    from bunny_upload import _setup_logging

    return run_gated_upload_workflow(
        source_root=source,
        output_root=output,
        report_path=report,
        workflow_report_path=wf_report,
        cdn_base=(args.cdn_base or "").strip(),
        path_prefix=(args.prefix or BUNNY_ROOT_FOLDER).strip(),
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
