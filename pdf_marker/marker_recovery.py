# -*- coding: utf-8 -*-
"""
Recover a marked PDF from a markers JSON file + the original (unmarked) PDF.

JSON alone does not contain PDF bytes — you must still have the same book PDF
that was open when the markers were saved.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

import fitz  # PyMuPDF

# (page_no 1-based, x_pdf, y_pdf, marker_no)
MarkerTuple = Tuple[int, float, float, int]


def apply_markers_to_fitz_document(doc: fitz.Document, items: List[MarkerTuple]) -> None:
    """Draw black square and white 3-digit label at each marker (same as PDF Marker Save PDF)."""
    npages = len(doc)
    half = 4.0
    for page_no, x_pdf, y_pdf, marker_no in items:
        if page_no < 1 or page_no > npages:
            continue
        page = doc[page_no - 1]
        r = fitz.Rect(x_pdf - half, y_pdf - half, x_pdf + half, y_pdf + half)
        page.draw_rect(r, color=(0, 0, 0), fill=(0, 0, 0), width=0)
        label = f"{marker_no:03d}"
        tw = 22.0
        label_rect = fitz.Rect(x_pdf - tw, y_pdf + half + 0.5, x_pdf + tw, y_pdf + half + 14.0)
        page.insert_textbox(
            label_rect,
            label,
            fontsize=9,
            fontname="helv",
            color=(1, 1, 1),
            align=fitz.TEXT_ALIGN_CENTER,
        )


def marker_tuples_from_markers_json(data: Dict[str, Any]) -> List[MarkerTuple]:
    """Parse PDF Marker markers JSON into tuples for embedding."""
    pages_obj = data.get("pages", {})
    if not isinstance(pages_obj, dict):
        return []
    items: List[MarkerTuple] = []
    for page_key, marker_list in pages_obj.items():
        try:
            page_no = int(page_key)
        except Exception:
            continue
        if not isinstance(marker_list, list):
            continue
        for entry in marker_list:
            if not isinstance(entry, dict):
                continue
            try:
                x = float(entry.get("x"))
                y = float(entry.get("y"))
            except Exception:
                continue
            try:
                marker_no = int(entry.get("marker", 0))
            except Exception:
                marker_no = 0
            if marker_no < 1:
                continue
            items.append((page_no, x, y, marker_no))
    return items


def load_markers_json_file(json_path: str) -> Dict[str, Any]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Invalid markers JSON: root must be an object.")
    return data


def guess_source_pdf_beside_json(json_path: str) -> str | None:
    """
    If JSON is named like `BookName_markers.json`, suggest `BookName.pdf` in the same folder.
    Also tries the JSON 'file' basename field when that PDF exists beside the JSON.
    """
    folder = os.path.dirname(os.path.abspath(json_path))
    base = os.path.splitext(os.path.basename(json_path))[0]
    if base.endswith("_markers"):
        stem = base[: -len("_markers")]
        candidate = os.path.join(folder, f"{stem}.pdf")
        if os.path.isfile(candidate):
            return candidate
    try:
        data = load_markers_json_file(json_path)
        hinted = data.get("file")
        if isinstance(hinted, str) and hinted.strip():
            stem = os.path.splitext(hinted.strip())[0]
            candidate = os.path.join(folder, f"{stem}.pdf")
            if os.path.isfile(candidate):
                return candidate
    except Exception:
        pass
    return None


def recover_marked_pdf_from_json_files(
    json_path: str,
    source_pdf_path: str,
    dest_pdf_path: str,
) -> Tuple[int, List[str]]:
    """
    Read markers from JSON, copy source PDF, draw markers, save dest.

    Returns (number of markers drawn, list of warning strings).
    """
    data = load_markers_json_file(json_path)
    raw_items = marker_tuples_from_markers_json(data)
    warnings: List[str] = []

    if not os.path.isfile(source_pdf_path):
        raise FileNotFoundError(f"Source PDF not found:\n{source_pdf_path}")

    doc = fitz.open(source_pdf_path)
    try:
        npages = len(doc)
        valid: List[MarkerTuple] = []
        skipped_page: List[int] = []
        for page_no, x, y, mno in raw_items:
            if page_no < 1 or page_no > npages:
                skipped_page.append(page_no)
                continue
            valid.append((page_no, x, y, mno))
        if skipped_page:
            warnings.append(
                f"Skipped {len(skipped_page)} marker(s) with page number out of range (PDF has {npages} page(s))."
            )

        if not valid:
            raise ValueError("No valid markers to apply (check JSON and that the PDF matches this book).")

        pdf_bytes = doc.write()
        out_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            apply_markers_to_fitz_document(out_doc, valid)
            out_doc.save(dest_pdf_path, garbage=4, deflate=True)
        finally:
            out_doc.close()
        return len(valid), warnings
    finally:
        doc.close()
