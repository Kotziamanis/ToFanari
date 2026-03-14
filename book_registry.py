# -*- coding: utf-8 -*-
"""ToFanari — Book Registry: load and validate book_registry.xlsx, map chapter codes to parent books."""

import os
from typing import Any, Dict, List, Optional, Tuple

try:
    import openpyxl
except ImportError:
    openpyxl = None

REQUIRED_COLUMNS = [
    "Book_Code",
    "Book_Title",
    "Book_Slug",
    "Thinkific_Course_Name",
    "Subscription_Group",
    "FlipBuilder_Book_Name",
    "Bookshelf_Name",
    "Bookshelf_Order",
    "Bunny_Root_Folder",
    "Chapter_List",
    "Is_Active",
    "Notes",
]

SHEET_NAME = "BOOKS"


def _cell_str(val: Any) -> str:
    """Convert cell value to string, strip whitespace."""
    if val is None:
        return ""
    return str(val).strip()


def _parse_chapter_list(chapter_list_str: str) -> List[str]:
    """Parse Chapter_List (e.g. 'AN01,AN02,AN03') into list of chapter codes."""
    if not chapter_list_str:
        return []
    parts = [p.strip() for p in chapter_list_str.split(",") if p.strip()]
    return parts


def load_book_registry(path: str) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
    """
    Load book_registry.xlsx from path.
    Returns: (ok, list of book rows, list of error messages).
    Each row is a dict with column names as keys.
    """
    errors: List[str] = []
    books: List[Dict[str, Any]] = []

    if not openpyxl:
        return (False, [], ["openpyxl is required. Install with: pip install openpyxl"])

    if not path or not os.path.isfile(path):
        return (False, [], [f"File not found: {path}"])

    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as e:
        return (False, [], [f"Failed to open file: {str(e)}"])

    if SHEET_NAME not in wb.sheetnames:
        wb.close()
        return (False, [], [f"Sheet '{SHEET_NAME}' not found in workbook."])

    ws = wb[SHEET_NAME]
    rows_iter = ws.iter_rows(min_row=1, values_only=True)

    header_row = next(rows_iter, None)
    if not header_row:
        wb.close()
        return (False, [], ["Sheet BOOKS is empty."])

    header = [_cell_str(c) for c in header_row]
    col_idx = {h: i for i, h in enumerate(header) if h}

    for req in REQUIRED_COLUMNS:
        if req not in col_idx:
            wb.close()
            return (False, [], [f"Required column '{req}' not found."])

    seen_book_codes: set = set()
    seen_book_slugs: set = set()
    chapter_to_books: Dict[str, List[str]] = {}

    for row_idx, row in enumerate(rows_iter, start=2):
        if not row:
            continue
        vals = list(row) + [None] * (len(header) - len(row))
        book: Dict[str, Any] = {}
        for col in REQUIRED_COLUMNS:
            idx = col_idx.get(col, -1)
            book[col] = _cell_str(vals[idx]) if idx >= 0 else ""

        book_code = book.get("Book_Code", "")
        book_slug = book.get("Book_Slug", "")
        chapter_list_str = book.get("Chapter_List", "")

        if not book_code:
            errors.append(f"Row {row_idx}: Book_Code is empty.")
        elif book_code in seen_book_codes:
            errors.append(f"Row {row_idx}: Duplicate Book_Code: {book_code}")
        else:
            seen_book_codes.add(book_code)

        if not book_slug:
            errors.append(f"Row {row_idx}: Book_Slug is empty.")
        elif book_slug in seen_book_slugs:
            errors.append(f"Row {row_idx}: Duplicate Book_Slug: {book_slug}")
        else:
            seen_book_slugs.add(book_slug)

        if not chapter_list_str:
            errors.append(f"Row {row_idx}: Chapter_List is empty.")

        chapters = _parse_chapter_list(chapter_list_str)
        for ch in chapters:
            if ch not in chapter_to_books:
                chapter_to_books[ch] = []
            chapter_to_books[ch].append(book_code)

        books.append(book)

    wb.close()

    for ch, codes in chapter_to_books.items():
        if len(codes) > 1:
            errors.append(
                f"Chapter code {ch} appears in more than one book in book_registry.xlsx"
            )

    ok = len(errors) == 0
    return (ok, books, errors)


def _ensure_registry_file(path: str) -> Tuple[bool, Any, List[str]]:
    """
    Open or create book_registry.xlsx. Returns (ok, workbook, errors).
    Caller must close workbook after use.
    """
    errors: List[str] = []
    if not openpyxl:
        return (False, None, ["openpyxl is required. Install with: pip install openpyxl"])

    if not path or not path.strip():
        return (False, None, ["No file path specified."])

    path = path.strip()
    if os.path.isfile(path):
        try:
            wb = openpyxl.load_workbook(path)
            return (True, wb, [])
        except Exception as e:
            return (False, None, [f"Failed to open file: {str(e)}"])
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = SHEET_NAME
        for col, name in enumerate(REQUIRED_COLUMNS, 1):
            ws.cell(row=1, column=col, value=name)
        return (True, wb, [])


def append_book_to_registry(path: str, book: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Append a new book row to book_registry.xlsx. Creates file if it does not exist.
    Returns: (ok, list of error messages).
    Validation: Book_Code, Book_Title, Book_Slug, Chapter_List required; no duplicate Book_Code or Book_Slug.
    """
    errors: List[str] = []

    book_code = (book.get("Book_Code") or "").strip()
    book_title = (book.get("Book_Title") or "").strip()
    book_slug = (book.get("Book_Slug") or "").strip()
    chapter_list = (book.get("Chapter_List") or "").strip()

    if not book_code:
        errors.append("Book_Code is required.")
    if not book_title:
        errors.append("Book_Title is required.")
    if not book_slug:
        errors.append("Book_Slug is required.")
    if not chapter_list:
        errors.append("Chapter_List is required.")

    if errors:
        return (False, errors)

    ok, wb, load_errs = _ensure_registry_file(path)
    if not ok or not wb:
        return (False, load_errs)

    try:
        ws = wb[SHEET_NAME] if SHEET_NAME in wb.sheetnames else wb.active
        if ws.title != SHEET_NAME:
            ws = wb.create_sheet(SHEET_NAME)
        header = [ws.cell(row=1, column=c).value for c in range(1, len(REQUIRED_COLUMNS) + 1)]
        if not header or header[0] is None:
            for col, name in enumerate(REQUIRED_COLUMNS, 1):
                ws.cell(row=1, column=col, value=name)
        next_row = ws.max_row + 1
        header_row = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
        col_idx = {str(h).strip(): i for i, h in enumerate(header_row) if h}
        code_col = col_idx.get("Book_Code", 0) + 1
        slug_col = col_idx.get("Book_Slug", 2) + 1
        existing_codes = set()
        existing_slugs = set()
        for r in range(2, next_row):
            code_val = ws.cell(row=r, column=code_col).value
            slug_val = ws.cell(row=r, column=slug_col).value
            if code_val:
                existing_codes.add(str(code_val).strip())
            if slug_val:
                existing_slugs.add(str(slug_val).strip())
        if book_code in existing_codes:
            return (False, [f"Duplicate Book_Code: {book_code}"])
        if book_slug in existing_slugs:
            return (False, [f"Duplicate Book_Slug: {book_slug}"])

        values = [
            book.get("Book_Code", ""),
            book.get("Book_Title", ""),
            book.get("Book_Slug", ""),
            book.get("Thinkific_Course_Name", ""),
            book.get("Subscription_Group", ""),
            book.get("FlipBuilder_Book_Name", ""),
            book.get("Bookshelf_Name", ""),
            book.get("Bookshelf_Order", ""),
            book.get("Bunny_Root_Folder", ""),
            book.get("Chapter_List", ""),
            book.get("Is_Active", ""),
            book.get("Notes", ""),
        ]
        for col, val in enumerate(values, 1):
            ws.cell(row=next_row, column=col, value=val if val is not None else "")
        wb.save(path)
        return (True, [])
    except Exception as e:
        return (False, [str(e)])


def find_book_for_chapter(
    chapter_code: str, books: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Given a chapter code (e.g. AN01), return the matching book registry row.
    Returns None if not found or if chapter appears in multiple books (caller should validate first).
    """
    if not chapter_code or not books:
        return None
    ch = str(chapter_code).strip()
    if not ch:
        return None
    found = None
    for book in books:
        chapter_list_str = book.get("Chapter_List", "")
        chapters = _parse_chapter_list(chapter_list_str)
        if ch in chapters:
            if found is not None:
                return None
            found = book
    return found
