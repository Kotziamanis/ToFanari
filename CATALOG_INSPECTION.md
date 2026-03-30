# Parameters Catalog Inspection

## Current settings/parameters.json (BEFORE cleaning)

### Collections (1 in file)
| Code        | Title        | Type                          |
|-------------|--------------|-------------------------------|
| MINAIO      | Μηναίο       | **Default seed / demo**       |

### Books (12 in file)
| Code   | Title        | Collection | Slug      | Type                          |
|--------|--------------|------------|-----------|-------------------------------|
| MIN_01 | Ιανουάριος   | MINAIO     | minaio-01 | **Default seed** (Jan)        |
| MIN_02 | Φεβρουάριος  | MINAIO     | minaio-02 | **Default seed** (Feb)        |
| MIN_03 | Μάρτιος      | MINAIO     | minaio-03 | **Default seed** (Mar)        |
| MIN_04 | Απρίλιος     | MINAIO     | minaio-04 | **Default seed** (Apr)        |
| MIN_05 | Μάιος        | MINAIO     | minaio-05 | **Default seed** (May)        |
| MIN_06 | Ιούνιος      | MINAIO     | minaio-06 | **Default seed** (Jun)        |
| MIN_07 | Ιούλιος      | MINAIO     | minaio-07 | **Default seed** (Jul)        |
| MIN_08 | Αύγουστος    | MINAIO     | minaio-08 | **Default seed** (Aug)        |
| MIN_09 | Σεπτέμβριος  | MINAIO     | minaio-09 | **Default seed** (Sep)        |
| MIN_10 | Οκτώβριος    | MINAIO     | minaio-10 | **Default seed** (Oct)        |
| MIN_11 | Νοέμβριος    | MINAIO     | minaio-11 | **Default seed** (Nov)        |
| MIN_12 | Δεκέμβριος   | MINAIO     | minaio-12 | **Default seed** (Dec)        |

### Runtime injection (not in file)

When `load_parameters()` runs, `_ensure_pilot_books()` **injects** these if missing:
- Collection: **PARAKLITIKOI** (Παρακλητικοί)
- Book: **MIKP** (Μικρός Παρακλητικός Κανών) — pilot
- Book: **MEPK** (Μέγας Παρακλητικός Κανών) — pilot

---

## Why the app shows 14 books and 2 collections

| Source                    | Count | Content                                      |
|---------------------------|-------|----------------------------------------------|
| **File (saved data)**     | 1 coll, 12 books | MINAIO + MIN_01..MIN_12                  |
| **Runtime injection**     | 1 coll, 2 books  | PARAKLITIKOI + MIKP + MEPK               |
| **Total at runtime**      | 2 coll, 14 books |                                              |

---

## Where the 14 books came from

1. **12 books (MIN_01..MIN_12)** — **Default seed data**
   - Created when `parameters.json` did not exist
   - `load_parameters()` → `_default_parameters()` wrote MINAIO + 12 months
   - This is the built-in demo structure

2. **2 books (MIKP, MEPK)** — **Runtime injection**
   - Not stored in the file
   - Added in memory each time by `_ensure_pilot_books()` when loading
   - Implemented as pilot/test books

3. **No imports** — Nothing came from Excel or other imports

---

## Classification (app vs. workflow)

| config.py `_NON_PROD_SLUGS` | Matches? | Result          |
|-----------------------------|----------|-----------------|
| example_book, demo, test, sample, fixture, sandbox, placeholder | None of our slugs match | All 14 treated as "production" for upload |

For **workflow testing**, you want only the pilot books (MIKP, optionally MEPK).

---

## Clean pilot catalog (prepared)

Contains **ONLY**:
- 1 collection: **PARAKLITIKOI** (Παρακλητικοί)
- 1 book: **MIKP** (Μικρός Παρακλητικός Κανών)
- (Optional) 1 book: **MEPK** (Μέγας Παρακλητικός Κανών)

Ready to replace `settings/parameters.json` after your confirmation.
