# Tofanari Suite (monorepo)

This repository hosts **three separate products** (one purpose each). **Do not mix** their code or dependencies — see **`ARCHITECTURE.md`** and **`APPLICATIONS.txt`**.

**Repository (canonical):** [github.com/Kotziamanis/tofanari-suite](https://github.com/Kotziamanis/tofanari-suite)

Renaming from the old **`ToFanari`** repo on GitHub, or fixing your local `git remote`? See **[GITHUB_RENAME.md](GITHUB_RENAME.md)**.

---

## 1. PDF Marker

**Purpose:** Open a PDF, place audio-player position markers by hand, save PDF (and optional JSON). Nothing else.

| Goal | How |
|------|-----|
| Run from source | `python main.py` (launcher) or `python pdf_marker/main.py` — **3.10+**; `pip install -r pdf_marker/requirements.txt` |
| Build Windows `.exe` | `build_pdf_marker_windows.bat` → `dist\PDFMarkerTool.exe` |
| Download `.exe` (CI) | [Actions → Artifacts](https://github.com/Kotziamanis/tofanari-suite/actions/workflows/build-pdf-marker-windows.yml) |

---

## 2. Synch-tool

**Not implemented in this folder.** Reserved name only — see **`synch-tool/README.md`**.

---

## 3. Tofanari Main Tool

**Purpose:** Full publishing workflow (parameters, PDF pipeline, database, Bunny prep, etc.).

| Goal | How |
|------|-----|
| Run from source | `python app.py` or `python tofanari_main_tool.py` (Python **3.10+**; install deps as in `requirements.txt` + project needs) |
| Build portable folder / zip | `python build_new_version.py` → `release\TofanariMainTool\` and `TofanariMainTool_portable.zip` |

Window title and in-app header use **Tofanari Main Tool**.

---

## Work on PC

**→ [WORK_ON_PC.md](WORK_ON_PC.md)** — clone, venv, run apps, build EXEs.

---

## Requirements

- **Python 3.10+** recommended
- **PDF Marker only:** `pip install -r pdf_marker/requirements.txt`
- **Tofanari Main Tool (or full dev checkout):** `pip install -r requirements.txt`
