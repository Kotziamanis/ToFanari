# -*- coding: utf-8 -*-
"""
Tofanari Main Tool — Central Parameters System.

Persistent master catalog (JSON) defining:
- Collections (e.g. MINAIO, Μηναίο)
- Books (code, title, collection, expected_chapters, chapters, active, display_order)
- Book-to-collection mapping (each book belongs to ONE collection or is standalone)
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from config import get_settings_dir

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(get_settings_dir(), "parameters.json")


@dataclass
class ChapterDef:
    """Single chapter definition."""
    order: int
    code: str
    title: str
    active: bool = True


@dataclass
class BookDef:
    """Book definition in Parameters."""
    code: str
    title: str
    collection: Optional[str] = None  # collection_code or null for standalone
    expected_chapters: int = 1
    active: bool = True
    display_order: int = 0
    book_slug: str = ""  # For Bunny/imported_chapters (e.g. min_01, minaio-01)
    chapters: List[ChapterDef] = field(default_factory=list)
    # Optional legacy fields
    thinkific_course_name: str = ""
    flipbuilder_book_name: str = ""
    bunny_root_folder: str = ""


@dataclass
class CollectionDef:
    """Collection definition."""
    collection_code: str
    title: str
    display_order: int = 0


def _ensure_pilot_books(data: Dict[str, Any]) -> None:
    """Ensure PARAKLITIKOI + MIKP, MEPK exist (for testing)."""
    coll_codes = {c.get("collection_code") for c in data.get("collections", []) if c.get("collection_code")}
    book_codes = {b.get("code") for b in data.get("books", []) if b.get("code")}
    if "PARAKLITIKOI" not in coll_codes:
        data["collections"].append({"collection_code": "PARAKLITIKOI", "title": "Παρακλητικοί", "display_order": 99})
    for code, title, slug, ch_code in [
        ("MIKP", "Μικρός Παρακλητικός Κανών", "MIKP", "MIKP_001"),
        ("MEPK", "Μέγας Παρακλητικός Κανών", "MEPK", "MEPK_001"),
    ]:
        if code not in book_codes:
            data["books"].append({
                "code": code, "title": title, "collection": "PARAKLITIKOI",
                "expected_chapters": 1, "active": True, "display_order": 99,
                "book_slug": slug, "chapters": [{"order": 1, "code": ch_code, "title": "", "active": True}],
            })


def _ensure_settings_dir() -> str:
    get_settings_dir()  # ensures folder exists
    return DEFAULT_PATH


def _default_parameters() -> Dict[str, Any]:
    """Default parameters: MINAIO + PARAKLITIKOI (pilot: MIKP, MEPK)."""
    months = [
        ("MIN_01", "Ιανουάριος", "minaio-01"),
        ("MIN_02", "Φεβρουάριος", "minaio-02"),
        ("MIN_03", "Μάρτιος", "minaio-03"),
        ("MIN_04", "Απρίλιος", "minaio-04"),
        ("MIN_05", "Μάιος", "minaio-05"),
        ("MIN_06", "Ιούνιος", "minaio-06"),
        ("MIN_07", "Ιούλιος", "minaio-07"),
        ("MIN_08", "Αύγουστος", "minaio-08"),
        ("MIN_09", "Σεπτέμβριος", "minaio-09"),
        ("MIN_10", "Οκτώβριος", "minaio-10"),
        ("MIN_11", "Νοέμβριος", "minaio-11"),
        ("MIN_12", "Δεκέμβριος", "minaio-12"),
    ]
    collections = [
        {"collection_code": "MINAIO", "title": "Μηναίο", "display_order": 1},
        {"collection_code": "PARAKLITIKOI", "title": "Παρακλητικοί", "display_order": 2},
    ]
    books = []
    for i, (code, title, slug) in enumerate(months):
        books.append({
            "code": code,
            "title": title,
            "collection": "MINAIO",
            "expected_chapters": 1,
            "active": True,
            "display_order": i + 1,
            "book_slug": slug,
            "chapters": [{"order": 1, "code": code, "title": "", "active": True}],
        })
    # Pilot books: MIKP, MEPK (Παρακλητικοί) — chapter codes use BOOKCODE_001 format
    paraklitikoi_books = [
        ("MIKP", "Μικρός Παρακλητικός Κανών", "MIKP", 1, "MIKP_001"),
        ("MEPK", "Μέγας Παρακλητικός Κανών", "MEPK", 1, "MEPK_001"),
    ]
    for i, (code, title, slug, exp_ch, ch_code) in enumerate(paraklitikoi_books):
        books.append({
            "code": code,
            "title": title,
            "collection": "PARAKLITIKOI",
            "expected_chapters": exp_ch,
            "active": True,
            "display_order": i + 1,
            "book_slug": slug,
            "chapters": [{"order": 1, "code": ch_code, "title": "", "active": True}],
        })
    return {
        "collections": collections,
        "books": books,
        "schema_version": 1,
    }


def _norm_book_code(s: str) -> str:
    """Normalize book code to uppercase for consistency."""
    return (s or "").strip().upper()


def _norm_chapter_code(s: str) -> str:
    """Normalize chapter code to uppercase for consistency."""
    return (s or "").strip().upper()


def _book_to_registry_format(book: Dict[str, Any]) -> Dict[str, Any]:
    """Convert parameters book to book_registry format (Book_Slug, chapters as ChapterDef). All codes uppercase."""
    from book_registry import ChapterDef as BRChapterDef
    chs = book.get("chapters") or []
    chapter_defs = []
    # If chapters empty but chapter_list exists, parse it (e.g. "MIKP_001,MIKP_002")
    if not chs and (book.get("chapter_list") or book.get("Chapter_List") or "").strip():
        ch_list_str = (book.get("chapter_list") or book.get("Chapter_List") or "").strip()
        for i, code in enumerate(ch_list_str.split(",")):
            code = _norm_chapter_code(code)
            if code:
                chapter_defs.append(BRChapterDef(order=i + 1, code=code, title="", active=True))
    code_upper = _norm_book_code(book.get("code") or "")
    for c in chs:
        if isinstance(c, dict):
            code = _norm_chapter_code(c.get("code") or "")
            # Legacy: if chapter code equals book code and single chapter, use BOOKCODE_001 format
            if code == code_upper and len(chs) == 1:
                code = f"{code_upper}_001"
            chapter_defs.append(BRChapterDef(
                order=c.get("order", 1),
                code=code,
                title=(c.get("title") or "").strip(),
                active=c.get("active", True),
            ))
        elif hasattr(c, "code"):
            code = _norm_chapter_code(getattr(c, "code", ""))
            if code == code_upper and len(chs) == 1:
                code = f"{code_upper}_001"
            chapter_defs.append(BRChapterDef(order=c.order, code=code, title=c.title or "", active=getattr(c, "active", True)))
    raw_slug = (book.get("book_slug") or book.get("code") or "").strip()
    slug = _norm_book_code(raw_slug.replace("-", "_")).replace("_", "-") if raw_slug else code_upper
    return {
        "Book_Code": code_upper,
        "Book_Title": (book.get("title") or "").strip(),
        "Book_Slug": slug or code_upper,
        "Chapter_List": ",".join(c.code for c in chapter_defs),
        "chapters": chapter_defs,
        "expected_chapters_count": book.get("expected_chapters", len(chapter_defs)),
        "collection": book.get("collection"),
        "display_order": book.get("display_order", 0),
        "Is_Active": "1" if book.get("active", True) else "0",
        "Thinkific_Course_Name": book.get("thinkific_course_name", ""),
        "FlipBuilder_Book_Name": book.get("flipbuilder_book_name", ""),
        "Bunny_Root_Folder": book.get("bunny_root_folder", ""),
    }


def load_parameters(path: str = None) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    Load parameters from JSON.
    Returns (ok, data, errors).
    data has: collections, books, schema_version.
    Creates default file if missing.
    """
    p = path or DEFAULT_PATH
    errors: List[str] = []
    if not os.path.isfile(p):
        _ensure_settings_dir()
        default = _default_parameters()
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2, ensure_ascii=False)
            return (True, default, [])
        except Exception as e:
            return (False, {}, [f"Could not create default parameters: {e}"])
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return (False, {}, ["Invalid parameters: root must be object"])
        data.setdefault("collections", [])
        data.setdefault("books", [])
        data.setdefault("schema_version", 1)
        _ensure_pilot_books(data)
        return (True, data, [])
    except json.JSONDecodeError as e:
        return (False, {}, [f"Invalid JSON: {e}"])
    except Exception as e:
        return (False, {}, [str(e)])


def save_parameters(data: Dict[str, Any], path: str = None) -> bool:
    """Save parameters to JSON."""
    p = path or DEFAULT_PATH
    _ensure_settings_dir()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def get_books_as_registry_format(books: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert parameters books to book_registry format (for app compatibility)."""
    return [_book_to_registry_format(b) for b in books]


def get_collections_sorted(collections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return collections sorted by display_order."""
    return sorted(collections, key=lambda c: (c.get("display_order", 999), c.get("collection_code", "")))


def get_books_sorted(
    books: List[Dict[str, Any]],
    collection_code: Optional[str] = None,
    active_only: bool = True,
) -> List[Dict[str, Any]]:
    """
    Return books sorted by display_order.
    If collection_code given, filter to that collection.
    If collection_code is None, return only standalone books (collection is null/empty).
    """
    filtered = []
    for b in books:
        if active_only and not b.get("active", True):
            continue
        if collection_code is not None:
            if (b.get("collection") or "").strip() == collection_code:
                filtered.append(b)
        else:
            if not (b.get("collection") or "").strip():
                filtered.append(b)
    return sorted(filtered, key=lambda x: (x.get("display_order", 999), x.get("code", "")))


def load_catalog_from_parameters(path: str = None) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
    """
    Load catalog from parameters.json in book_registry format.
    Returns (ok, books, errors). Books have Book_Code, Book_Slug, chapters, etc.
    """
    ok, data, errors = load_parameters(path)
    if not ok:
        return (False, [], errors)
    books_raw = data.get("books", [])
    books = get_books_as_registry_format(books_raw)
    return (True, books, [])


def get_collection_completeness(
    data: Dict[str, Any],
    get_imported_fn,
) -> List[Dict[str, Any]]:
    """
    For each collection, compute completeness based on all its books.
    get_imported_fn(book_slug) -> list of imported chapter codes.
    Returns list of {collection_code, title, books, complete_count, total_count, status}.
    """
    from book_registry import compare_imported_vs_expected, ChapterDef
    structure = get_bookshelf_structure(data)
    result = []
    for coll in structure["collections"]:
        complete = 0
        total = len(coll["books"])
        for b in coll["books"]:
            slug = (b.get("book_slug") or b.get("code") or "").strip()
            expected = b.get("chapters") or []
            ch_defs = []
            for c in expected:
                if isinstance(c, dict):
                    ch_defs.append(ChapterDef(
                        order=c.get("order", 1),
                        code=(c.get("code") or "").strip(),
                        title=(c.get("title") or "").strip(),
                        active=c.get("active", True),
                    ))
            imported = get_imported_fn(slug) if slug else []
            cmp_res = compare_imported_vs_expected(b.get("code", ""), ch_defs, imported)
            if cmp_res.get("merge_allowed"):
                complete += 1
        status = "COMPLETE" if complete == total else ("INCOMPLETE" if complete > 0 else "MISSING")
        result.append({
            "collection_code": coll["collection_code"],
            "title": coll["title"],
            "complete_count": complete,
            "total_count": total,
            "status": status,
        })
    return result


def get_bookshelf_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build structure for collection-first bookshelf UI:
    - top_level: [collections] + [standalone books]
    - collections: [{code, title, display_order, books: [...]}]
    - standalone: [books with no collection]
    """
    collections = get_collections_sorted(data.get("collections", []))
    books = data.get("books", [])
    result = {
        "collections": [],
        "standalone_books": get_books_sorted(books, collection_code=None),
    }
    for coll in collections:
        code = (coll.get("collection_code") or "").strip()
        if not code:
            continue
        coll_books = get_books_sorted(books, collection_code=code)
        result["collections"].append({
            "collection_code": code,
            "title": coll.get("title", code),
            "display_order": coll.get("display_order", 0),
            "books": coll_books,
        })
    return result
