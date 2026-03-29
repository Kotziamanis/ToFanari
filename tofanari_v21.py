# -*- coding: utf-8 -*-
"""
ToFanari — Βυζαντινή Μουσική  v2.1  (FINAL)
Δρ. Ανδρέας Κυριακίδης — To Fanari Byzantine Music School

Τι κάνει:
  • Εντοπίζει τον δείκτη ■ (U+25A0) στο PDF που εξάγετε από Melodos
  • Τοποθετεί αριθμημένα κόκκινα κουμπιά σε κάθε θέση ■
  • Καλύπτει τον ■ με λευκό ορθογώνιο (δεν φαίνεται στο τελικό PDF)
  • Δημιουργεί database.xlsx για Bunny.net / Thinkific

Εγκατάσταση βιβλιοθηκών (μία φορά):
  pip install pymupdf openpyxl
"""

import tkinter as tk

from app import App


def main():
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
