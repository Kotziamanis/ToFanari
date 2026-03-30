# -*- coding: utf-8 -*-
"""
Backward-compatible launcher for **PDF Marker** only.

Implementation lives in `pdf_marker/` — this repo root file exists so
`python main.py` keeps working. Do not add imports from Tofanari Main Tool here.
"""

from __future__ import annotations

import os
import runpy


def _run() -> None:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdf_marker", "main.py")
    runpy.run_path(path, run_name="__main__")


if __name__ == "__main__":
    _run()
