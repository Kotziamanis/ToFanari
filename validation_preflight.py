
# -*- coding: utf-8 -*-
"""ToFanari — Preflight validation for database and source structure (platform-independent)."""

import os
import re
from typing import Any, Dict, List

# Row dict: song_title, mp3_code, mp3_file, url, page, y, preview_text (optional)

# Extract leading 3-digit number from source MP3 filename: "001 Title.mp3" -> "001"
_SOURCE_MP3_NUMBER_RE = re.compile(r"^(\d{3})\s")


def _source_mp3_number_to_filename(mp3_files: List[str]) -> Dict[str, str]:
    r"""Build mapping from 3-digit source number (e.g. '001') to filename. Uses regex r'^(\d{3})\s'."""
    num_to_file: Dict[str, str] = {}
    for f in mp3_files or []:
        m = _SOURCE_MP3_NUMBER_RE.match(f)
        if m:
            num_to_file[m.group(1)] = f
    return num_to_file


def validate_database(
    rows: List[Dict[str, Any]],
    mp3_folder: str,
    source_mp3_files: List[str] = None,
) -> Dict[str, Any]:
    """
    Validate database integrity: required fields, source MP3 number matching, duplicates.
    Uses same source MP3 scan as Tab 4. Row i (1-based) must have a source file with number 001, 002, ...
    Returns: { "ok": bool, "rows_checked": int, "errors": [...], "warnings": [...], "info": [] }
    """
    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []
    n = len(rows)
    if n == 0:
        return {
            "ok": False,
            "rows_checked": 0,
            "errors": ["No hymn rows to validate."],
            "warnings": [],
            "info": [],
        }

    source_num_to_file = _source_mp3_number_to_filename(source_mp3_files) if source_mp3_files else {}

    seen_titles: Dict[str, List[int]] = {}
    seen_codes: Dict[str, List[int]] = {}
    seen_files: Dict[str, List[int]] = {}
    seen_urls: Dict[str, List[int]] = {}

    for i, row in enumerate(rows):
        row_num = i + 1
        song_title = (row.get("song_title") or "").strip()
        mp3_code = (row.get("mp3_code") or "").strip()
        mp3_file = (row.get("mp3_file") or "").strip()
        url = (row.get("url") or "").strip()
        page = row.get("page")
        y = row.get("y")

        # 1. Required fields — Song Title may be empty before Tab 5 Ανανέωση (title fill from MP3)
        if not song_title and not (mp3_code or mp3_file):
            errors.append(f"Row {row_num}: missing Song Title.")
        if not mp3_code:
            errors.append(f"Row {row_num}: missing MP3 Code.")
        if page is None and row.get("page") is None:
            pass  # optional
        elif page is not None and (not isinstance(page, (int, float)) or page < 1):
            errors.append(f"Row {row_num}: invalid or missing page/marker reference.")

        # 2. Source MP3 number matching: row 1 -> 001, row 2 -> 002, ... (same logic as Tab 4)
        if source_mp3_files is not None:
            num_str = f"{row_num:03d}"
            if num_str not in source_num_to_file:
                errors.append(f"Row {row_num} has no matching source MP3 file (missing source MP3 number: {num_str}).")
        elif not mp3_file:
            errors.append(f"Row {row_num}: missing MP3 File.")

        # 3. File existence only when not using source list (legacy path): check mp3_file in folder
        if not source_mp3_files and mp3_file and mp3_folder:
            path = os.path.join(mp3_folder, mp3_file)
            if not os.path.isfile(path):
                errors.append(f"Row {row_num}: file not found in MP3 folder: {mp3_file}")

        # 4. Duplicate detection (collect for later)
        if song_title:
            seen_titles.setdefault(song_title, []).append(row_num)
        if mp3_code:
            seen_codes.setdefault(mp3_code, []).append(row_num)
        if mp3_file:
            seen_files.setdefault(mp3_file, []).append(row_num)
        if url:
            seen_urls.setdefault(url, []).append(row_num)

        # 5. Empty/broken row
        if not song_title and not mp3_code and not mp3_file:
            errors.append(f"Row {row_num}: incomplete/broken row (no title, code, or file).")

    # Summary: Song Titles not yet populated (Tab 5 Ανανέωση not run)
    empty_title_with_mp3 = sum(
        1 for r in rows
        if not (r.get("song_title") or "").strip() and ((r.get("mp3_code") or "").strip() or (r.get("mp3_file") or "").strip())
    )
    if empty_title_with_mp3:
        warnings.append(
            f"{empty_title_with_mp3} row(s) have empty Song Title. Run Tab 5 Ανανέωση to populate from MP3 filenames."
        )

    # Report duplicates
    for title, indices in seen_titles.items():
        if len(indices) > 1:
            errors.append(f"Duplicate Song Title: '{title}' at rows {indices}.")
    for code, indices in seen_codes.items():
        if len(indices) > 1:
            errors.append(f"Duplicate MP3 Code: '{code}' at rows {indices}.")
    for f, indices in seen_files.items():
        if len(indices) > 1:
            errors.append(f"Duplicate MP3 File: '{f}' at rows {indices}.")
    for u, indices in seen_urls.items():
        if len(indices) > 1:
            errors.append(f"Duplicate URL at rows {indices}.")

    # Optional URL summary
    no_url = sum(1 for r in rows if not (r.get("url") or "").strip())
    if no_url:
        warnings.append(f"{no_url} row(s) have no optional URL.")

    return {
        "ok": len(errors) == 0,
        "rows_checked": n,
        "errors": errors,
        "warnings": warnings,
        "info": info,
    }


def validate_source_structure(
    rows: List[Dict[str, Any]],
    mp3_file_count: int,
) -> Dict[str, Any]:
    """
    Validate source structure: page/marker ordering, row vs MP3 count, broken rows.
    No preview-length or short-preview warnings (preview text is optional).
    Returns: { "ok": bool, "errors": [...], "warnings": [...], "info": [...] }
    """
    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []
    n = len(rows)

    if n == 0:
        return {"ok": True, "errors": [], "warnings": [], "info": ["No rows to validate."]}

    # 1. Page/marker ordering
    prev_page, prev_y = None, None
    for i, row in enumerate(rows):
        page, y = row.get("page"), row.get("y")
        if page is not None and prev_page is not None and page < prev_page:
            warnings.append(f"Row {i + 1}: page {page} is less than previous page {prev_page}.")
        if page == prev_page and y is not None and prev_y is not None and y < prev_y:
            warnings.append(f"Row {i + 1}: Y value moves backwards.")
        if page is not None:
            prev_page = page
        if y is not None:
            prev_y = y

    # 2. Hymn rows vs source MP3 files (NOT PDF page count)
    if mp3_file_count is not None and mp3_file_count != n:
        delta = mp3_file_count - n
        warnings.append(f"Hymn row count: {n}")
        warnings.append(f"Source MP3 files: {mp3_file_count}")
        if delta > 0:
            warnings.append(f"More MP3 files than hymn rows: {delta}")
        else:
            warnings.append(f"Fewer MP3 files than hymn rows: {abs(delta)} missing")
    info.append(f"Hymn row count: {n}")
    info.append(f"Source MP3 files: {mp3_file_count if mp3_file_count is not None else 'N/A'}")

    # 3. Broken/incomplete row (no title and no file)
    for i, row in enumerate(rows):
        has_title = bool((row.get("song_title") or "").strip())
        has_file = bool((row.get("mp3_file") or "").strip())
        if not has_title and not has_file:
            errors.append(f"Row {i + 1}: broken/incomplete (no title, no file).")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "info": info,
    }


# Hymn boundary validation thresholds (heuristic)
BEGINNING_MATCH_CHARS = 35 # adjacent rows matching up to this many chars → duplicate beginning
OVERLAP_MIN_CHARS = 25     # min overlap length to consider boundary overlap


def validate_hymn_boundaries(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Heuristic validation of hymn boundaries (PDF splitting/parsing).
    Detects duplicate beginnings, boundary overlap, repeated page/span. No preview-length checks.
    Returns: { "errors": [...], "warnings": [...], "info": [...] }
    """
    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []
    n = len(rows)

    if n == 0:
        return {"errors": [], "warnings": [], "info": ["No rows for boundary validation."]}

    previews = [(row.get("preview_text") or "").strip() for row in rows]
    pages = [row.get("page") for row in rows]
    ys = [row.get("y") for row in rows]

    # 1. Adjacent duplicate beginnings (first N chars identical or very similar)
    for i in range(n - 1):
        a, b = previews[i], previews[i + 1]
        if not a or not b:
            continue
        prefix_len = min(BEGINNING_MATCH_CHARS, len(a), len(b))
        if prefix_len < 10:
            continue
        if a[:prefix_len].strip() and b[:prefix_len].strip() and a[:prefix_len] == b[:prefix_len]:
            warnings.append(
                f"Rows {i + 1} and {i + 2}: adjacent duplicate beginnings (first {prefix_len} chars match)."
            )
        # Very similar: allow tiny difference (e.g. whitespace)
        a_start = a[:prefix_len].replace(" ", "").replace("\n", "")
        b_start = b[:prefix_len].replace(" ", "").replace("\n", "")
        if len(a_start) >= 10 and a_start == b_start and a[:prefix_len] != b[:prefix_len]:
            warnings.append(
                f"Rows {i + 1} and {i + 2}: adjacent very similar preview beginnings."
            )

    # 4. Boundary overlap suspicion (row i end overlaps row i+1 start)
    for i in range(n - 1):
        a, b = previews[i], previews[i + 1]
        if len(a) < OVERLAP_MIN_CHARS or len(b) < OVERLAP_MIN_CHARS:
            continue
        overlap_found = False
        for L in range(OVERLAP_MIN_CHARS, min(len(a), len(b)) + 1):
            suffix_a = a[-L:]
            prefix_b = b[:L]
            if suffix_a == prefix_b and L >= OVERLAP_MIN_CHARS:
                overlap_found = True
                break
            # Partial: suffix of a appears at start of b with high ratio
            if suffix_a in b[: L + 20] and L >= OVERLAP_MIN_CHARS:
                overlap_found = True
                break
        if overlap_found:
            warnings.append(
                f"Rows {i + 1} and {i + 2}: boundary overlap suspicion — preview text overlaps."
            )

    # 4. Repeated page/marker span (adjacent rows same page and same or very close y)
    for i in range(n - 1):
        p1, p2 = pages[i], pages[i + 1]
        y1, y2 = ys[i], ys[i + 1]
        if p1 is None or p2 is None:
            continue
        if p1 == p2 and y1 is not None and y2 is not None:
            if y1 == y2:
                warnings.append(
                    f"Rows {i + 1} and {i + 2}: repeated page/marker span (same page {p1}, same Y {y1})."
                )
            else:
                try:
                    diff = abs(float(y1) - float(y2))
                    if diff < 1.0:
                        warnings.append(
                            f"Rows {i + 1} and {i + 2}: same page {p1} with very close Y values."
                        )
                except (TypeError, ValueError):
                    pass

    info.append(f"Boundary checks: begin_match={BEGINNING_MATCH_CHARS}, overlap>={OVERLAP_MIN_CHARS}.")

    return {"errors": errors, "warnings": warnings, "info": info}


# Regex to extract leading number from source MP3 filename: "001 Title.mp3" -> 1, "010 Another.mp3" -> 10
_MP3_LEADING_NUMBER_RE = re.compile(r"^(\d+)")
# Pattern "NNN Title.mp3": digits, space, title, .mp3
_MP3_VALID_PATTERN_RE = re.compile(r"^\d+\s+.+\.mp3$", re.IGNORECASE)


def validate_mp3_filename_pattern(mp3_files: List[str]) -> Dict[str, Any]:
    """
    Check filenames against pattern NNN Title.mp3.
    Returns: { "errors": [], "warnings": [...], "info": [] }
    """
    errors: List[str] = []
    warnings: List[str] = []
    invalid: List[str] = []
    for f in mp3_files:
        if not _MP3_VALID_PATTERN_RE.match(f):
            invalid.append(f)
    for fn in invalid:
        warnings.append(f"Invalid filename (expected NNN Title.mp3): {fn}")
    return {"errors": errors, "warnings": warnings, "info": []}


def validate_mp3_numbering(source_mp3_files: List[str]) -> Dict[str, Any]:
    r"""
    Validate MP3 numbering from source filenames.
    Uses regex r'^(\d+)' to extract leading number.
    Reports: missing numbers, duplicate numbers, non-numbered source files.
    Returns: { "errors": [], "warnings": [...], "info": [] }
    """
    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []

    if not source_mp3_files:
        return {"errors": errors, "warnings": warnings, "info": info}

    # A. Non-numbered source files
    numbered: List[tuple[int, str]] = []  # (number, filename)
    for f in source_mp3_files:
        m = _MP3_LEADING_NUMBER_RE.match(f)
        if m:
            try:
                numbered.append((int(m.group(1)), f))
            except ValueError:
                warnings.append(f"Source MP3 without leading number: {f}")
        else:
            warnings.append(f"Source MP3 without leading number: {f}")

    if not numbered:
        return {"errors": errors, "warnings": warnings, "info": info}

    # B. Duplicate numbers
    num_to_files: Dict[int, List[str]] = {}
    for n, fn in numbered:
        num_to_files.setdefault(n, []).append(fn)
    for n, fns in sorted(num_to_files.items()):
        if len(fns) > 1:
            width = max(3, len(str(max(num_to_files))))
            warnings.append(f"Duplicate MP3 number: {n:0{width}d}")

    # C. Missing numbers
    numbers_sorted = sorted(num_to_files.keys())
    min_n, max_n = numbers_sorted[0], numbers_sorted[-1]
    present = set(numbers_sorted)
    width = max(3, len(str(max_n)))
    for n in range(min_n, max_n + 1):
        if n not in present:
            warnings.append(f"Missing MP3 number: {n:0{width}d}")

    return {"errors": errors, "warnings": warnings, "info": info}


def validate_row_mp3_count_consistency(
    rows: List[Dict[str, Any]],
    mp3_folder: str,
    mp3_file_count: int,
) -> Dict[str, Any]:
    """
    Compare hymn row count with source MP3 file count.
    Uses mp3_file_count passed from caller (from Tab 4 MP3 scan) — no listdir here.
    Returns: { "errors": [...], "warnings": [...], "info": [...] }
    """
    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []

    hymn_row_count = len(rows)

    matched_count = sum(
        1 for r in rows
        if (r.get("mp3_file") or "").strip()
    )

    if hymn_row_count == 0:
        info.append("No hymn rows; row/MP3 count check skipped.")
        return {"errors": errors, "warnings": warnings, "info": info}

    # Hymn rows vs source MP3 files (NOT PDF page count)
    if hymn_row_count != mp3_file_count:
        warnings.append(f"Hymn row count: {hymn_row_count}")
        warnings.append(f"Source MP3 files: {mp3_file_count}")
        if mp3_file_count > hymn_row_count:
            warnings.append(f"More MP3 files than hymn rows: {mp3_file_count - hymn_row_count}")
        else:
            warnings.append(f"Fewer MP3 files than hymn rows: {hymn_row_count - mp3_file_count} missing")

    # Matched rows vs hymn rows
    if matched_count < hymn_row_count:
        warnings.append(
            f"Only {matched_count} of {hymn_row_count} hymn rows have MP3 assignments."
        )

    info.append(f"Hymn row count: {hymn_row_count}")
    info.append(f"Source MP3 files: {mp3_file_count}")
    info.append(f"Rows with MP3 File field populated: {matched_count}")

    return {"errors": errors, "warnings": warnings, "info": info}


def run_full_validation(
    rows: List[Dict[str, Any]],
    mp3_folder: str = None,
    mp3_files: List[str] = None,
    mp3_count: int = None,
    pdf_path: str = None,
) -> Dict[str, Any]:
    """
    Run all validation layers (database, source structure, hymn boundaries, row/MP3 count).
    Uses single MP3 folder (selected in Tab 4); mp3_files used for numbering/pattern checks.
    """
    all_errors: List[str] = []
    all_warnings: List[str] = []
    all_info: List[str] = []

    # INFO: MP3 folder
    validation_info: List[str] = []
    validation_info.append(f"MP3 folder: {mp3_folder if mp3_folder else 'N/A'}")
    validation_info.append(f"MP3 files: {mp3_count if mp3_count is not None else 0}")
    if pdf_path:
        validation_info.append(f"PDF path: {pdf_path}")

    if not mp3_folder or not mp3_folder.strip():
        all_warnings.append("No MP3 folder selected (Tab 4).")

    db = validate_database(rows, mp3_folder or "", source_mp3_files=mp3_files)
    src = validate_source_structure(rows, mp3_count)
    bnd = validate_hymn_boundaries(rows)
    cnt = validate_row_mp3_count_consistency(rows, mp3_folder or "", mp3_count or 0)
    gaps = validate_mp3_numbering(mp3_files or [])
    pattern_res = validate_mp3_filename_pattern(mp3_files or [])

    all_errors = (db.get("errors") or []) + (src.get("errors") or []) + (bnd.get("errors") or []) + (cnt.get("errors") or []) + (gaps.get("errors") or []) + (pattern_res.get("errors") or [])
    all_warnings = (db.get("warnings") or []) + (src.get("warnings") or []) + (bnd.get("warnings") or []) + (cnt.get("warnings") or []) + (gaps.get("warnings") or []) + (pattern_res.get("warnings") or [])
    all_info = validation_info + (db.get("info") or []) + (src.get("info") or []) + (bnd.get("info") or []) + (cnt.get("info") or []) + (gaps.get("info") or []) + (pattern_res.get("info") or [])
    n = db.get("rows_checked", len(rows))

    ok = len(all_errors) == 0
    has_warnings = len(all_warnings) > 0

    if ok and not has_warnings:
        status_kind = "ok"
        status_text = "DATABASE OK — YOU MAY PROCEED"
    elif ok and has_warnings:
        status_kind = "warnings"
        status_text = "DATABASE OK WITH WARNINGS — REVIEW BEFORE PROCEEDING"
    else:
        status_kind = "errors"
        status_text = "DATABASE NOT READY — FIX ERRORS FIRST"

    report_lines = [
        "DATABASE VALIDATION REPORT",
        "",
        f"Rows checked: {n}",
        f"MP3 folder: {mp3_folder if mp3_folder else 'N/A'}",
        f"MP3 files: {mp3_count if mp3_count is not None else 'N/A'}",
        f"Matched rows: {n}",
        "",
        f"Errors: {len(all_errors)}",
        f"Warnings: {len(all_warnings)}",
        "",
        f"STATUS: {status_text}",
        "",
    ]
    if all_errors:
        report_lines.append("--- ERRORS ---")
        report_lines.extend(all_errors)
        report_lines.append("")
    if all_warnings:
        report_lines.append("--- WARNINGS ---")
        report_lines.extend(all_warnings)
        report_lines.append("")
    if all_info:
        report_lines.append("--- INFO ---")
        report_lines.extend(all_info)

    return {
        "ok": ok,
        "status_kind": status_kind,
        "status_text": status_text,
        "report_lines": report_lines,
        "errors": all_errors,
        "warnings": all_warnings,
        "info": all_info,
        "rows_checked": n,
    }
