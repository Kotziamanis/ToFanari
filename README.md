# ToFanari

PDF marker tool, full desktop publishing workflow (ToFanari), Bunny prep, and GitHub Actions build for a standalone **Windows `.exe`**.

**Repository:** [github.com/Kotziamanis/ToFanari](https://github.com/Kotziamanis/ToFanari)

---

## Work on PC (recommended)

You do **not** need a Mac. Everything lives in this repo and on your PC drives.

**→ Start here:** **[WORK_ON_PC.md](WORK_ON_PC.md)** — install Python, clone the repo, run the apps, build `PDFMarkerTool.exe`, use Cursor.

---

## Quick links

| Goal | How |
|------|-----|
| Run PDF Marker from source | `python main.py` (after venv + `pip install -r requirements.txt`) |
| Run full ToFanari app | `python app.py` (Python **3.10+**) |
| Build `PDFMarkerTool.exe` locally | `build_pdf_marker_windows.bat` |
| Download `.exe` without building | [Actions → Artifacts](https://github.com/Kotziamanis/ToFanari/actions/workflows/build-pdf-marker-windows.yml) |
| Short PC cheat sheet | [PC_DOWNLOAD_CHEATSHEET.txt](PC_DOWNLOAD_CHEATSHEET.txt) |

---

## Requirements

- **Python 3.10 or newer** (for `app.py`; `main.py` is best on 3.10+ too)
- Dependencies: `pip install -r requirements.txt`
