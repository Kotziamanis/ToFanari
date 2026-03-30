# Architecture — three independent applications

This repository is a **monorepo** with **strict separation**. Each app has **one purpose** and must not depend on the others’ UI or business logic.

## 1. PDF Marker

| | |
|---|---|
| **Purpose** | Mark positions on a PDF for a future audio player. |
| **Entry** | `python main.py` (launcher at repo root) or `python pdf_marker/main.py` |
| **Code** | `pdf_marker/main.py`, `pdf_marker/marker_recovery.py`, `pdf_marker/recover_pdf_from_json.py` |
| **Dependencies** | `pdf_marker/requirements.txt` (PyMuPDF + Pillow only) |
| **Must not import** | `app.py`, `config.py`, `database.py`, `pdf_ops.py`, or any main-tool–only module. |

## 2. Synch-tool

| | |
|---|---|
| **Purpose** | (Reserved — not implemented here.) |
| **Code** | `synch-tool/README.txt` — placeholder only. |
| **Dependencies** | N/A in this repo. |

## 3. Tofanari Main Tool

| | |
|---|---|
| **Purpose** | Full publishing workflow: parameters, PDF pipeline with ■ markers, database, Bunny prep, etc. |
| **Entry** | `python app.py` or `python tofanari_main_tool.py` |
| **Code** | `app.py`, `config.py`, `database.py`, `pdf_ops.py`, `validators.py`, and related modules at repo root. |
| **Dependencies** | Root `requirements.txt` (includes `openpyxl` and libraries used by `app.py`). |
| **Must not import** | `pdf_marker` package — the marker GUI is a separate product. PDF operations inside the main tool use **`pdf_ops.py`**, not `pdf_marker/main.py`. |

## Coupling rules

1. **No imports** from `pdf_marker` → main tool, or main tool → `pdf_marker` (except humans copying ideas; no `import` edges).
2. **Shared third-party libs** (e.g. PyMuPDF) may appear in both `requirements` files; that is not “mixing apps,” only overlapping tools.
3. **GitHub Actions** builds the PDF Marker EXE from `pdf_marker/pdf_marker.spec` only; main tool builds use `tofanari.spec` / `build_new_version.py`.

See also **`APPLICATIONS.txt`**.
