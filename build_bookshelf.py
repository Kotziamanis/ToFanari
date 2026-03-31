#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ToFanari — Build bookshelf from Parameters.

Reads settings/parameters.json and generates:
- bookshelf/assets/js/books-data.js
- bookshelf/index.html (collection-first: collections + standalone books)

Collection-first UI:
- Index shows: collection cards + standalone book cards
- Click collection → category page with books inside
- Click standalone book → open Flipbook directly
"""

import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARAMETERS_PATH = os.path.join(SCRIPT_DIR, "settings", "parameters.json")
BOOKSHELF_DIR = os.path.join(SCRIPT_DIR, "bookshelf")
BOOKS_DATA_JS = os.path.join(BOOKSHELF_DIR, "assets", "js", "books-data.js")
INDEX_HTML = os.path.join(BOOKSHELF_DIR, "index.html")
CATEGORIES_DIR = os.path.join(BOOKSHELF_DIR, "categories")
# Root-relative flipbook URLs (same Pull Zone as bookshelf): /flipbooks/<slug>/index.html
FLIPBOOK_BASE_PATH = "/flipbooks"


def slug_to_key(slug: str) -> str:
    """Convert book_slug to JS-safe key (e.g. minaio-01 -> minaio01)."""
    return re.sub(r"[^a-z0-9]", "", (slug or "").lower())


def load_parameters():
    with open(PARAMETERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_bookshelf_structure(data):
    from parameters import get_collections_sorted, get_books_sorted
    collections = get_collections_sorted(data.get("collections", []))
    books = data.get("books", [])
    result = {"collections": [], "standalone_books": get_books_sorted(books, collection_code=None)}
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


def build_books_data_js(structure):
    """Generate BOOKS_DATA structure for render-books.js."""
    lines = ["/** Auto-generated from parameters.json. Do not edit manually. */", ""]
    lines.append("window.BOOKS_DATA = {")
    for coll in structure["collections"]:
        key = coll["collection_code"].lower()
        title = coll["title"]
        books_js = []
        for b in coll["books"]:
            slug = (b.get("book_slug") or b.get("code") or "").strip()
            book_title = (b.get("title") or "").strip()
            flip_url = f"{FLIPBOOK_BASE_PATH}/{slug}/index.html" if slug else "#"
            cover = f"assets/images/{slug}.svg" if slug else "assets/images/placeholder.svg"
            books_js.append(
                f'            {{ id: "{slug_to_key(slug)}", title: "{_esc(book_title)}", '
                f'subtitle: "", cover: "{cover}", '
                f'flipbookUrl: "{flip_url}" }}'
            )
        lines.append(f'    {key}: {{')
        lines.append(f'        title: "{_esc(title)}",')
        lines.append("        books: [")
        lines.append(",\n".join(books_js))
        lines.append("        ]")
        lines.append("    },")
    lines.append("};")
    return "\n".join(lines)


def _esc(s):
    return (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def build_index_html(structure):
    """Generate collection-first index: collections + standalone books."""
    cards = []
    for coll in structure["collections"]:
        key = coll["collection_code"].lower()
        title = coll["title"]
        subtitle = f"{len(coll['books'])} βιβλία"
        cards.append(
            f'        <a href="categories/{key}.html" class="category-card">\n'
            f'            <span class="category-icon">📖</span>\n'
            f'            <h2>{title}</h2>\n'
            f'            <p>{subtitle}</p>\n'
            f'        </a>'
        )
    for b in structure["standalone_books"]:
        slug = (b.get("book_slug") or b.get("code") or "").strip()
        title = (b.get("title") or "").strip()
        flip_url = f"{FLIPBOOK_BASE_PATH}/{slug}/index.html" if slug else "#"
        cards.append(
            f'        <a href="{flip_url}" class="category-card book-direct" target="_blank" rel="noopener">\n'
            f'            <span class="category-icon">📕</span>\n'
            f'            <h2>{title}</h2>\n'
            f'            <p>Ανεξάρτητο βιβλίο</p>\n'
            f'        </a>'
        )
    cards_html = "\n".join(cards)
    return f'''<!DOCTYPE html>
<html lang="el">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ToFanari — Βιβλιοθήκη Βυζαντινής Μουσικής</title>
    <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
    <header class="site-header">
        <h1>Ηχώ του Βυζαντίου</h1>
        <p class="tagline">Βιβλιοθήκη Βυζαντινής Μουσικής</p>
    </header>

    <main class="categories-grid">
{cards_html}
    </main>

    <footer class="site-footer">
        <p>Το Φανάρι — Ψηφιακή Βιβλιοθήκη Βυζαντινής Μουσικής</p>
    </footer>
</body>
</html>'''


def ensure_category_page(collection_code: str, title: str, books: list):
    """Ensure category HTML page exists for collection."""
    os.makedirs(CATEGORIES_DIR, exist_ok=True)
    key = collection_code.lower()
    path = os.path.join(CATEGORIES_DIR, f"{key}.html")
    content = f'''<!DOCTYPE html>
<html lang="el">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — ToFanari</title>
    <link rel="stylesheet" href="../assets/css/style.css">
</head>
<body>
    <main class="category-page">
        <div class="page-header">
            <a href="../index.html" class="back-link">← Κατηγορίες</a>
            <h1 class="page-title">{title}</h1>
        </div>
        <div class="bookshelf">
            <div id="books-grid" class="books-grid"></div>
        </div>
    </main>
    <script>window.CATEGORY_KEY = '{key}'; window.ASSET_BASE = '../';</script>
    <script src="../assets/js/books-data.js"></script>
    <script src="../assets/js/render-books.js"></script>
</body>
</html>'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    if not os.path.isfile(PARAMETERS_PATH):
        print(f"Parameters not found: {PARAMETERS_PATH}")
        print("Run the app first to create default parameters.")
        return 1
    data = load_parameters()
    structure = get_bookshelf_structure(data)
    js_content = build_books_data_js(structure)
    os.makedirs(os.path.dirname(BOOKS_DATA_JS), exist_ok=True)
    with open(BOOKS_DATA_JS, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"Wrote {BOOKS_DATA_JS}")
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(build_index_html(structure))
    print(f"Wrote {INDEX_HTML}")
    for coll in structure["collections"]:
        ensure_category_page(coll["collection_code"], coll["title"], coll["books"])
        print(f"Ensured category page: {coll['collection_code']}")
    print("Bookshelf build complete.")
    return 0


if __name__ == "__main__":
    exit(main())
