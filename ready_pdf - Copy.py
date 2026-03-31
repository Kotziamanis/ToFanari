# -*- coding: utf-8 -*-
"""
ToFanari — Ready PDF validation for already-prepared chapter PDFs.

Validates that a PDF is suitable for the pipeline: exists, has markers,
valid numbering, can be associated with book/chapter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from pdf_ops import Marker, detect_markers
from validators import (
    validate_duplicate_positions,
    validate_empty_book_code,
    validate_page_numbers,
)


@dataclass
class ReadyPdfValidationResult:
    """Result of validating an already-prepared chapter PDF."""
    pdf_path: str
    passed: bool
    markers: List[Marker] = field(default_factory=list)
    marker_count: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    report_lines: List[str] = field(default_factory=list)


def validate_ready_pdf(
    pdf_path: str,
    chapter_code: Optional[str] = None,
) -> ReadyPdfValidationResult:
    """
    Validate an already-prepared chapter PDF for use in the pipeline.

    Checks:
    - PDF exists and is readable
    - Markers (■) are present
    - Marker numbering/positions are valid (no duplicates, valid pages)
    - Chapter code format is valid (if provided)

    Returns ReadyPdfValidationResult with passed=True only if all checks pass.
    """
    r = ReadyPdfValidationResult(pdf_path=pdf_path, passed=False)
    lines: List[str] = []

    # 1. Exists
    if not pdf_path or not pdf_path.strip():
        r.errors.append("No PDF path provided.")
        r.report_lines = ["READY PDF VALIDATION — FAIL", "", "Errors:", *r.errors]
        return r

    if not os.path.isfile(pdf_path):
        r.errors.append(f"PDF file does not exist: {pdf_path}")
        r.report_lines = ["READY PDF VALIDATION — FAIL", "", "Errors:", *r.errors]
        return r

    if not pdf_path.lower().endswith(".pdf"):
        r.warnings.append("File does not have .pdf extension.")

    lines.append("READY PDF VALIDATION REPORT")
    lines.append("")
    lines.append(f"PDF: {pdf_path}")
    lines.append("")

    # 2. Detect markers
    try:
        markers = detect_markers(pdf_path)
    except Exception as e:
        r.errors.append(f"Could not read PDF: {e}")
        r.report_lines = lines + ["FAIL", "", "Errors:", *r.errors]
        return r

    r.markers = markers
    r.marker_count = len(markers)

    if not markers:
        r.errors.append("No markers (■) found in PDF. The PDF may not be prepared for ToFanari.")
        r.report_lines = lines + ["FAIL", "", "Markers found: 0", "", "Errors:", *r.errors]
        return r

    lines.append(f"Markers found: {r.marker_count}")
    lines.append("")

    # 3. Validate numbering / positions
    ok_dup, msg_dup = validate_duplicate_positions(markers)
    ok_page, msg_page = validate_page_numbers(markers)
    seq_ok = ok_dup and ok_page
    lines.append(f"Marker sequence: {'OK' if seq_ok else 'ERROR'}")
    if not ok_dup:
        r.errors.append(msg_dup)
    if not ok_page:
        r.errors.append(msg_page)
    lines.append("")

    # 4. Chapter code (optional at validation; required for association)
    if chapter_code is not None and (chapter_code or "").strip():
        ok_code, msg_code = validate_empty_book_code(chapter_code.strip())
        if not ok_code:
            r.errors.append(msg_code)

    # Summary
    if r.errors:
        r.passed = False
        lines.append("RESULT: FAIL")
        lines.append("")
        lines.append("Errors:")
        lines.extend(r.errors)
        if r.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(r.warnings)
    else:
        r.passed = True
        lines.append("RESULT: PASS")
        lines.append("")
        lines.append("The PDF is ready for use. Associate with book/chapter to continue.")
        if r.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(r.warnings)

    r.report_lines = lines
    return r
