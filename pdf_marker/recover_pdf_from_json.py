# -*- coding: utf-8 -*-
"""
One-off CLI: build a marked PDF from markers JSON + original PDF (no GUI).

  python recover_pdf_from_json.py markers.json source.pdf output_marked.pdf

If you only saved JSON by mistake, use this once, or use the app button
"Recover PDF from JSON".
"""

from __future__ import annotations

import sys

from marker_recovery import recover_marked_pdf_from_json_files


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "Usage: python recover_pdf_from_json.py <markers.json> <source.pdf> <output.pdf>",
            file=sys.stderr,
        )
        return 2
    _, json_path, src, dest = sys.argv
    try:
        n, warnings = recover_marked_pdf_from_json_files(json_path, src, dest)
        print(f"OK: wrote {n} marker(s) to {dest}")
        for w in warnings:
            print("Warning:", w)
        return 0
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
