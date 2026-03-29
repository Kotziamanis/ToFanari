# Work on PC only (no Mac needed)

Use this as your single checklist. Your **PDFs and books stay on the PC** — only this project folder comes from GitHub (or you copy files into `source_books/` etc. as you like).

---

## 1. One-time installs on Windows

Install these **once** on the PC you use for development:

| What | Why | Link / action |
|------|-----|----------------|
| **Git for Windows** | Clone & push the repo | [git-scm.com/download/win](https://git-scm.com/download/win) |
| **Python 3.12 (64-bit)** | Run `main.py` / `app.py` | [python.org/downloads/windows](https://www.python.org/downloads/windows/) — tick **“Add python.exe to PATH”** during setup |
| **Cursor** (optional) | Same AI editor as on Mac | [cursor.com](https://cursor.com) |

You do **not** need anything copied from the Mac.

---

## 2. Get the project (first time)

Open **PowerShell** or **Command Prompt** in the folder where you keep code, e.g. `Documents\GitHub`:

```bat
git clone https://github.com/Kotziamanis/ToFanari.git
cd ToFanari
```

To update later (pull latest from GitHub):

```bat
cd ToFanari
git pull
```

---

## 3. Python environment (recommended)

From the `ToFanari` folder:

**Option A — helper script**

Double-click **`setup_windows.bat`** (creates `.venv` and installs dependencies).

Then before each session:

```bat
.venv\Scripts\activate.bat
```

**Option B — manual**

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Run the PDF Marker tool (source)

With venv activated:

```bat
python main.py
```

- **Open PDF** — pick files from **any drive** (your existing PC folders).
- **Save PDF** / **Save JSON** — outputs go where you choose in the dialog.

No Mac involved.

---

## 5. Run the full ToFanari application

Requires **Python 3.10+** (for `str | None` syntax in `app.py`):

```bat
python app.py
```

---

## 6. Build `PDFMarkerTool.exe` on this PC

With venv activated and dependencies installed:

```bat
build_pdf_marker_windows.bat
```

Output: **`dist\PDFMarkerTool.exe`** — you can copy that file anywhere (another PC, USB) **without** installing Python there.

---

## 7. Download the `.exe` from GitHub (no build)

If you only want the pre-built program:

1. Open:  
   [github.com/Kotziamanis/ToFanari/actions/workflows/build-pdf-marker-windows.yml](https://github.com/Kotziamanis/ToFanari/actions/workflows/build-pdf-marker-windows.yml)
2. Open the latest run with a **green** check.
3. **Artifacts** → **PDFMarkerTool-Windows-x64** → download ZIP → extract **`PDFMarkerTool.exe`**.

Use **`PC_DOWNLOAD_CHEATSHEET.txt`** as a short reminder.

---

## 8. Open this folder in Cursor (optional)

1. Install Cursor on Windows.
2. **File → Open Folder** → select your `ToFanari` clone.
3. Work with the AI assistant the same way as on Mac — the project is identical.

---

## 9. Daily routine (develop on PC)

1. `git pull` — get changes if you pushed from elsewhere or a collaborator updated the repo.
2. Activate `.venv`, run `python main.py` or `python app.py`.
3. Save your PDFs / JSON / exports in your normal PC folders (or under `source_books\`, `settings\`, etc.).
4. When you change code: `git add`, `git commit`, `git push` (use a **Personal Access Token** with **repo** + **workflow** scopes if GitHub asks for a password).

---

## 10. What you can ignore

- **`build_pdf_marker_mac.command`**, **`Run_PDF_Marker_Tool.command`** — only for Mac; not needed on PC.
- **Mac `.app`** — not used on Windows.

---

## 11. If something fails

| Problem | Try |
|---------|-----|
| `python` not found | Reinstall Python and enable **Add to PATH**, or use `py -3.12` instead of `python`. |
| `ModuleNotFoundError: fitz` | Run `pip install -r requirements.txt` inside your venv. |
| `app.py` syntax errors | Use Python **3.10+** (not 3.9). |
| Git push rejected (workflow) | Create a token with **repo** + **workflow** at [github.com/settings/tokens](https://github.com/settings/tokens). |

---

You are set: **PC + GitHub + optional Cursor** is enough; the Mac is optional.
