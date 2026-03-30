#!/bin/bash
# Run the marker tool without building an .app (uses same Python rules as the build script).
set -e
cd "$(dirname "$0")"

pick_python() {
  local py candidates
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
  echo "No Python with working Tk found. Install from python.org/macOS or: brew install python-tk"
  echo "Then run this script again (or use build_pdf_marker_mac.command for the full .app)."
  read -r -p "Press Enter to close…"
  exit 1
fi

echo "Using: $PY"
"$PY" -m pip install -q pymupdf Pillow 2>/dev/null || true
exec "$PY" main.py
