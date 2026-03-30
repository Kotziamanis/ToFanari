# PDF Marker (standalone app)

**One purpose:** open a PDF, place markers for audio-player positions, save PDF (and optional JSON). Nothing else.

## Run

From repository root:

```bat
python main.py
```

(or `python pdf_marker\main.py` on Windows)

## Dependencies (only this app)

```bat
pip install -r pdf_marker/requirements.txt
```

Do **not** install the main-tool requirements unless you also run `app.py`.

## Code in this folder

| File | Role |
|------|------|
| `main.py` | Tkinter UI |
| `marker_recovery.py` | JSON → marked PDF recovery |
| `recover_pdf_from_json.py` | CLI for recovery |
| `pdf_marker.spec` | PyInstaller for `PDFMarkerTool.exe` |

## Boundaries

- **Must not** import `app.py`, `config.py`, or any module used only by Tofanari Main Tool.
- Tofanari Main Tool **must not** import from `pdf_marker` (it uses `pdf_ops.py` for its own PDF workflow).
