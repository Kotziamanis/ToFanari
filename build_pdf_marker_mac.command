#!/bin/bash
# Build PDF Marker Tool.app — must use a Python with working Tk (not Apple CLT python3).
set -e
cd "$(dirname "$0")"

pick_python() {
  local py candidates msg
  candidates=(
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
    "/opt/homebrew/opt/python@3.13/bin/python3.13"
    "/opt/homebrew/opt/python@3.12/bin/python3.12"
    "/opt/homebrew/opt/python@3.11/bin/python3.11"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3"
  )
  for py in "${candidates[@]}"; do
    if [[ -x "$py" ]] && "$py" -c "import tkinter; tkinter.Tk().withdraw()" 2>/dev/null; then
      echo "$py"
      return 0
    fi
  done
  if command -v python3 >/dev/null 2>&1 && python3 -c "import tkinter; tkinter.Tk().withdraw()" 2>/dev/null; then
    echo "python3"
    return 0
  fi
  return 1
}

PY="$(pick_python)" || true

if [[ -z "$PY" ]]; then
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  This Mac’s default Python3 cannot run Tk (GUI) — the app would crash."
  echo "  (Apple Command Line Tools Python often shows: “macOS 26 … required”.)"
  echo ""
  echo "  Fix: install ONE of these, then run this script again:"
  echo ""
  echo "  • https://www.python.org/downloads/macos/  (installer — includes Tk)"
  echo "  • Terminal:  brew install python-tk"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  read -r -p "Press Enter to close…"
  exit 1
fi

echo "Using: $PY"
"$PY" -c "import sys; print('Python', sys.version.split()[0])"

echo ""
echo "Installing PyInstaller, PyMuPDF, Pillow…"
"$PY" -m pip install -q pyinstaller pymupdf Pillow

echo ""
echo "Building PDF Marker Tool.app …"
"$PY" -m PyInstaller --noconfirm --clean pdf_marker.spec

echo ""
echo "Done: $(pwd)/dist/PDF Marker Tool.app"
echo "If Gatekeeper blocks it: right-click the app → Open → Open."
open "dist"
read -r -p "Press Enter to close…"
