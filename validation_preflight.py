# -*- coding: utf-8 -*-
"""ToFanari — Preflight validation for database and source structure (platform-independent)."""

import os
from typing import Any, Dict, List

# Row dict: song_title, mp3_code, mp3_file, url, page, y, preview_text (optional)


def validate_database(rows: List[Dict[str, Any]], mp3_folder: str) -> Dict[str, Any]:
    """
    Validate database integrity: required fields, MP3 File == MP3 Code + ".mp3", file existence, duplicates.
    Returns: { "ok": bool, "rows_checked": int, "errors": [...], "warnings": [...], "info": [...] }
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
        if not mp3_file:
            errors.append(f"Row {row_num}: missing MP3 File.")
        if page is None and row.get("page") is None:
            pass  # optional
        elif page is not None and (not isinstance(page, (int, float)) or page < 1):
            errors.append(f"Row {row_num}: invalid or missing page/marker reference.")

        # 2. MP3 File must equal MP3 Code + ".mp3" (Song Title is human-readable, not compared to file)
        if mp3_code:
            expected_file = f"{mp3_code}.mp3"
            if mp3_file != expected_file:
                errors.append(
                    f"Row {row_num}: MP3 File does not match MP3 Code (expected {expected_file})."
                )

        # 3. File existence
        if mp3_file and mp3_folder:
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
    Validate source structure: preview text, duplicates, ordering, row vs file count.
    Returns: { "ok": bool, "errors": [...], "warnings": [...], "info": [...] }
    """
    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []
    n = len(rows)

    if n == 0:
        return {"ok": True, "errors": [], "warnings": [], "info": ["No rows to validate."]}

    # 1. Empty or nearly empty preview
    for i, row in enumerate(rows):
        preview = (row.get("preview_text") or "").strip()
        if len(preview) < 2 and (row.get("song_title") or row.get("mp3_file")):
            warnings.append(f"Row {i + 1}: empty or very short preview/source text.")
        elif len(preview) > 0 and len(preview) < 10:
            warnings.append(f"Row {i + 1}: suspiciously short preview text.")

    # 2. Duplicate or nearly identical preview text
    prev_preview = None
    for i, row in enumerate(rows):
        preview = (row.get("preview_text") or "").strip()
        if preview and prev_preview and preview == prev_preview:
            warnings.append(f"Rows {i + 1} and {i + 2}: identical preview text.")
        prev_preview = preview

    # 3. Page/marker ordering
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

    # 4. Row count vs MP3 file count
    if mp3_file_count is not None and mp3_file_count != n:
        warnings.append(
            f"Mismatch: {n} hymn rows vs {mp3_file_count} MP3 files in folder. "
            "Matched by row order."
        )
    info.append(f"Hymn rows: {n}, MP3 files in folder: {mp3_file_count if mp3_file_count is not None else 'N/A'}.")

    # 5. Broken/incomplete row
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
PREVIEW_SHORT_CHARS = 15   # preview shorter than this → unusually short
PREVIEW_LONG_CHARS = 500   # preview longer than this → possibly merged hymns
BEGINNING_MATCH_CHARS = 35 # adjacent rows matching up to this many chars → duplicate beginning
OVERLAP_MIN_CHARS = 25     # min overlap length to consider boundary overlap


def validate_hymn_boundaries(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Heuristic validation of hymn boundaries (PDF splitting/parsing).
    Detects unusually short/long previews, duplicate beginnings, boundary overlap, repeated page/span.
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

    # 1. Unusually short preview/source text
    for i, txt in enumerate(previews):
        if len(txt) > 0 and len(txt) < PREVIEW_SHORT_CHARS:
            warnings.append(
                f"Row {i + 1}: unusually short preview ({len(txt)} chars) — possible boundary/split issue."
            )

    # 2. Unusually long preview/source text (possible merged hymns)
    for i, txt in enumerate(previews):
        if len(txt) > PREVIEW_LONG_CHARS:
            warnings.append(
                f"Row {i + 1}: unusually long preview ({len(txt)} chars) — may contain merged hymns."
            )

    # 3. Adjacent duplicate beginnings (first N chars identical or very similar)
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

    # 5. Repeated page/marker span (adjacent rows same page and same or very close y)
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

    # Only hard error: row with no content at all but has slot (already in other validators; optional here)
    for i, row in enumerate(rows):
        txt = previews[i]
        has_identity = (row.get("song_title") or "").strip() or (row.get("mp3_file") or "").strip()
        if has_identity and len(txt) == 0 and (pages[i] is not None or ys[i] is not None):
            # Could add error; user said "do not block unless clearly broken". Empty preview with identity is warning.
            pass

    info.append(f"Boundary checks: short<{PREVIEW_SHORT_CHARS}, long>{PREVIEW_LONG_CHARS}, begin_match={BEGINNING_MATCH_CHARS}, overlap>={OVERLAP_MIN_CHARS}.")

    return {"errors": errors, "warnings": warnings, "info": info}


def validate_row_mp3_count_consistency(
    rows: List[Dict[str, Any]],
    mp3_folder: str,
    mp3_file_count: int,
) -> Dict[str, Any]:
    """
    Compare hymn row count with MP3 file count.
    Uses mp3_file_count passed from caller (from get_current_mp3_files) — no listdir here.
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

    # Hymn rows vs MP3 files
    if hymn_row_count != mp3_file_count:
        warnings.append(
            f"Hymn row count ({hymn_row_count}) does not match MP3 file count ({mp3_file_count})."
        )
    if hymn_row_count > mp3_file_count:
        warnings.append(
            f"More hymn rows than MP3 files — {hymn_row_count - mp3_file_count} hymn(s) may be missing audio."
        )
    if mp3_file_count > hymn_row_count:
        warnings.append(
            f"More MP3 files than hymn rows — {mp3_file_count - hymn_row_count} extra MP3 file(s) in folder."
        )

    # Matched rows vs hymn rows
    if matched_count < hymn_row_count:
        warnings.append(
            f"Only {matched_count} of {hymn_row_count} hymn rows have MP3 assignments."
        )

    info.append(
        f"Row/MP3 consistency: {hymn_row_count} hymn rows, {mp3_file_count} MP3 files, {matched_count} rows with MP3 File."
    )

    return {"errors": errors, "warnings": warnings, "info": info}


def run_full_validation(
    rows: List[Dict[str, Any]],
    mp3_folder: str,
    mp3_file_count: int,
    pdf_path: str = None,
    mp3_files_list: List[str] = None,
    total_mp3: int = None,
    source_mp3_count: int = None,
    generated_mp3_count: int = None,
) -> Dict[str, Any]:
    """
    Run all validation layers (database, source structure, hymn boundaries, row/MP3 count) and return combined result.
    mp3_file_count = source MP3 files (used for row comparison). total/source/generated shown in report when provided.
    """
    # Clear all aggregates before running checks (no accumulation across runs)
    all_errors: List[str] = []
    all_warnings: List[str] = []
    all_info: List[str] = []

    # Validation context — resolved folder and counts; show in report
    validation_info: List[str] = []
    validation_info.append(f"PDF path used: {pdf_path if pdf_path else 'N/A'}")
    validation_info.append(f"MP3 folder used: {mp3_folder}")
    validation_info.append(f"MP3 folder exists: {'yes' if (mp3_folder and os.path.isdir(mp3_folder)) else 'no'}")
    if total_mp3 is not None and source_mp3_count is not None and generated_mp3_count is not None:
        validation_info.append(f"Total MP3 files in folder: {total_mp3}")
        validation_info.append(f"Source MP3 files: {source_mp3_count}")
        validation_info.append(f"Generated internal MP3 files ignored: {generated_mp3_count}")
    else:
        validation_info.append(f"MP3 files found in active folder (source): {mp3_file_count}")
    if mp3_files_list is not None:
        if mp3_files_list:
            validation_info.append("First 10 source MP3 files: " + ", ".join(mp3_files_list[:10]))
        else:
            validation_info.append("First 10 source MP3 files: (none)")

    db = validate_database(rows, mp3_folder)
    src = validate_source_structure(rows, mp3_file_count)
    bnd = validate_hymn_boundaries(rows)
    cnt = validate_row_mp3_count_consistency(rows, mp3_folder, mp3_file_count)

    all_errors = (db.get("errors") or []) + (src.get("errors") or []) + (bnd.get("errors") or []) + (cnt.get("errors") or [])
    all_warnings = (db.get("warnings") or []) + (src.get("warnings") or []) + (bnd.get("warnings") or []) + (cnt.get("warnings") or [])
    all_info = validation_info + (db.get("info") or []) + (src.get("info") or []) + (bnd.get("info") or []) + (cnt.get("info") or [])
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

    mp3_count_str = str(mp3_file_count) if mp3_file_count is not None else "N/A"
    report_lines = [
        "DATABASE VALIDATION REPORT",
        "",
        f"Rows checked: {n}",
        f"Source MP3 files: {mp3_count_str}",
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
