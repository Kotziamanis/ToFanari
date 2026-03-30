# -*- coding: utf-8 -*-
"""
CLI wrapper for **PDF Marker** recovery script (implementation in `pdf_marker/`).

  python recover_pdf_from_json.py markers.json source.pdf output_marked.pdf
"""

from __future__ import annotations

import os
import runpy


if __name__ == "__main__":
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdf_marker", "recover_pdf_from_json.py")
    runpy.run_path(path, run_name="__main__")
