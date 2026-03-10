# -*- coding: utf-8 -*-
"""ToFanari — Main GUI application."""

import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List

try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None

from config import (
    APP_TITLE,
    VERSION,
    CREAM,
    DARK_RED,
    DEFAULT_BUNNY_BASE_URL,
    GOLD,
    GREY_LIGHT,
    GREY_MED,
    LIGHT_RED,
    MARKER,
    MID_RED,
    TEXT_DARK,
    WHITE,
    GREEN,
)
from database import (
    build_database_xlsx,
    preview_lines,
    validate_mp3_files,
    get_mp3_code,
    get_mp3_file,
    get_mp3_url,
)
from pdf_ops import (
    Marker,
    apply_markers,
    detect_markers,
    extract_preview_text,
    extract_hymn_preview_lines,
    render_page_thumbnail,
)
from validators import (
    validate_empty_book_code,
    validate_duplicate_positions,
    validate_page_numbers,
    validate_missing_mp3,
)


# ─────────────────────────── UI helpers ──────────────────────────────

def _btn(
    parent,
    text,
    command,
    bg=DARK_RED,
    fg=WHITE,
    fs=11,
    pady=8,
    width=None,
    big=False,
    **kw,
):
    font_size = 13 if big else fs
    b = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        font=("Arial", font_size, "bold"),
        relief="flat",
        cursor="hand2",
        pady=pady,
        activebackground=MID_RED,
        activeforeground=WHITE,
        **kw,
    )
    if width:
        b.config(width=width)
    return b


def _enable_clipboard_paste(root, widget):
    """Enable Ctrl+V, Shift+Insert, and right-click paste for Entry or Text widgets.
    Works with Greek and other keyboard layouts (keycode-based fallback).
    """
    def do_paste(event=None):
        try:
            widget.event_generate("<<Paste>>")
        except Exception:
            try:
                text = root.clipboard_get()
                if text:
                    if isinstance(widget, tk.Text):
                        if widget.selection_present():
                            widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                        widget.insert(tk.INSERT, text)
                    else:
                        if widget.selection_present():
                            widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                        widget.insert(tk.INSERT, text)
            except Exception:
                pass
        return "break"

    def on_key(event):
        # keycode 86 = physical V key; Ctrl mask = 0x4
        if event.keycode == 86 and (event.state & 0x4):
            if event.keysym.lower() != "v":
                do_paste(event)
                return "break"

    def show_context_menu(event):
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Επικόλληση", command=lambda: do_paste())
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    widget.bind("<Control-v>", lambda e: do_paste(e), add="+")
    widget.bind("<Control-V>", lambda e: do_paste(e), add="+")
    widget.bind("<Shift-Insert>", lambda e: do_paste(e), add="+")
    widget.bind("<Key>", on_key, add="+")
    widget.bind("<Button-3>", show_context_menu, add="+")
    if sys.platform == "darwin":
        widget.bind("<Command-v>", lambda e: do_paste(e), add="+")


# ─────────────────────────── Main Application ────────────────────────

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_TITLE}  {VERSION}")
        self.root.geometry("1000x760")
        self.root.configure(bg=CREAM)
        self.root.resizable(True, True)

        self.pdf_path = tk.StringVar()
        self.fold = tk.StringVar()
        self.status = tk.StringVar(value=f"Καλωσήρθατε στο {APP_TITLE} {VERSION}")
        self.mrks: List[Marker] = []
        self.assignments: List[dict] = []  # one per marker: song_title, echos, section (StringVars)

        self.dv = {
            "code": tk.StringVar(value="BOOK"),
            "bunny": tk.StringVar(value=DEFAULT_BUNNY_BASE_URL),
            "mp3_fold": tk.StringVar(),
        }

        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=DARK_RED, height=70)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="♪", bg=DARK_RED, fg=GOLD, font=("Arial", 28)).pack(
            side="left", padx=15
        )
        tf = tk.Frame(hdr, bg=DARK_RED)
        tf.pack(side="left")
        tk.Label(tf, text="ToFanari", bg=DARK_RED, fg=WHITE, font=("Georgia", 22, "bold")).pack(
            anchor="w"
        )
        tk.Label(
            tf,
            text="Βυζαντινή Μουσική — Σύστημα Ψηφιακών Βιβλίων",
            bg=DARK_RED,
            fg="#DDDDDD",
            font=("Arial", 10),
        ).pack(anchor="w")
        tk.Label(hdr, text=VERSION, bg=DARK_RED, fg=GOLD, font=("Arial", 10)).pack(
            side="right", padx=15
        )

        # Notebook
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=CREAM, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=GREY_LIGHT,
            foreground=TEXT_DARK,
            padding=[12, 6],
            font=("Arial", 10, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", DARK_RED)],
            foreground=[("selected", WHITE)],
        )
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True)

        self.tab1 = tk.Frame(nb, bg=CREAM)
        self.tab2 = tk.Frame(nb, bg=CREAM)
        self.tab3 = tk.Frame(nb, bg=CREAM)
        self.tab4 = tk.Frame(nb, bg=CREAM)
        self.tab5 = tk.Frame(nb, bg=CREAM)
        nb.add(self.tab1, text="  1. Επιλογή Βιβλίου  ")
        nb.add(self.tab2, text="  2. Σήμανση PDF  ")
        nb.add(self.tab3, text="  3. Έλεγχος Κουμπιών  ")
        nb.add(self.tab4, text="  4. Βάση Δεδομένων  ")
        nb.add(self.tab5, text="  5. Αντιστοίχιση Ύμνων  ")
        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._build_tab1()
        self._build_tab2()
        self._build_tab3()
        self._build_tab4()
        self._build_tab5()

        # Status bar
        sb = tk.Frame(self.root, bg=DARK_RED, height=28)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        tk.Label(
            sb,
            textvariable=self.status,
            bg=DARK_RED,
            fg=WHITE,
            font=("Arial", 9),
            anchor="w",
        ).pack(fill="x", padx=10, pady=4)

    def _section_header(self, parent, text: str):
        fr = tk.Frame(parent, bg=DARK_RED, height=42)
        fr.pack(fill="x")
        fr.pack_propagate(False)
        tk.Label(
            fr, text=text, bg=DARK_RED, fg=WHITE, font=("Arial", 13, "bold")
        ).pack(side="left", padx=15, pady=8)

    def _card(self, parent):
        c = tk.Frame(parent, bg=WHITE, bd=0)
        c.pack(fill="both", expand=True, padx=20, pady=16)
        return c

    def _label(self, parent, text: str):
        tk.Label(
            parent,
            text=text,
            bg=WHITE,
            fg=TEXT_DARK,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(10, 2))

    def _s(self, msg: str):
        self.status.set(msg)

    def _build_tab1(self):
        f = self.tab1
        self._section_header(f, "📚  Επιλογή Βιβλίου & Φακέλου")
        card = self._card(f)

        self._label(card, "Φάκελος εργασίας:")
        row = tk.Frame(card, bg=WHITE)
        row.pack(fill="x", pady=3)
        tk.Entry(
            row, textvariable=self.fold, font=("Arial", 10), bg=GREY_LIGHT, relief="flat", bd=5
        ).pack(side="left", fill="x", expand=True)
        _btn(row, "Αναζήτηση…", self._browse_folder, width=14).pack(side="right", padx=(6, 0))

        self._label(card, "Αρχείο PDF (με markers ■):")
        row2 = tk.Frame(card, bg=WHITE)
        row2.pack(fill="x", pady=3)
        tk.Entry(
            row2,
            textvariable=self.pdf_path,
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        ).pack(side="left", fill="x", expand=True)
        _btn(row2, "Επιλογή PDF…", self._browse_pdf, width=14).pack(side="right", padx=(6, 0))

        tk.Frame(card, bg=GREY_MED, height=1).pack(fill="x", pady=15)

        info = tk.Frame(card, bg=LIGHT_RED, bd=0)
        info.pack(fill="x", pady=6)
        tk.Label(
            info,
            text="Αντιγράψτε τον δείκτη ■ και επικολλήστε τον στο Melodos:",
            bg=LIGHT_RED,
            fg=DARK_RED,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(8, 2))
        copy_row = tk.Frame(info, bg=LIGHT_RED)
        copy_row.pack(anchor="w", padx=10, pady=(0, 8))
        tk.Label(
            copy_row, text="■", bg=LIGHT_RED, fg=DARK_RED, font=("Arial", 24)
        ).pack(side="left", padx=(0, 12))
        _btn(
            copy_row,
            "📋  Αντιγραφή ■",
            lambda: (
                self.root.clipboard_clear(),
                self.root.clipboard_append(MARKER),
                self._s("✅ Ο δείκτης ■ αντιγράφηκε!"),
            ),
            bg=GREEN,
            pady=6,
        ).pack(side="left")

    def _build_tab2(self):
        f = self.tab2
        self._section_header(f, "🔍  Εντοπισμός & Εφαρμογή Markers")
        card = self._card(f)

        _btn(
            card,
            "🔍  Εντοπισμός Markers ■ στο PDF",
            self._detect,
            big=True,
        ).pack(fill="x", pady=6)
        self.cnt_lbl = tk.Label(
            card, text="—", bg=WHITE, fg=DARK_RED, font=("Arial", 14, "bold")
        )
        self.cnt_lbl.pack(pady=6)
        tk.Frame(card, bg=GREY_MED, height=1).pack(fill="x", pady=10)
        _btn(
            card,
            "🖨️  Δημιουργία PDF με Κουμπιά",
            self._apply,
            big=True,
        ).pack(fill="x", pady=6)
        self.prog = ttk.Progressbar(
            card, orient="horizontal", length=400, mode="determinate"
        )
        self.prog.pack(pady=8)
        self.prog_lbl = tk.Label(
            card, text="", bg=WHITE, fg=TEXT_DARK, font=("Arial", 9)
        )
        self.prog_lbl.pack()

    def _build_tab3(self):
        f = self.tab3
        self._section_header(f, "✅  Έλεγχος & Διαχείριση Κουμπιών")
        card = self._card(f)
        _btn(card, "🔄  Ανανέωση Λίστας", self._refresh_list).pack(anchor="w", pady=4)
        lf = tk.Frame(card, bg=WHITE)
        lf.pack(fill="both", expand=True, pady=6)
        sb = tk.Scrollbar(lf)
        sb.pack(side="right", fill="y")
        self.lst = tk.Listbox(
            lf,
            yscrollcommand=sb.set,
            font=("Courier", 10),
            bg=GREY_LIGHT,
            fg=TEXT_DARK,
            selectbackground=DARK_RED,
            selectforeground=WHITE,
            relief="flat",
            bd=0,
        )
        self.lst.pack(fill="both", expand=True)
        sb.config(command=self.lst.yview)
        _btn(
            card,
            "⛔  Απενεργοποίηση / Ενεργοποίηση επιλεγμένου",
            self._toggle_keep,
            bg=MID_RED,
        ).pack(fill="x", pady=4)

    def _build_tab4(self):
        f = self.tab4
        self._section_header(f, "📊  Δημιουργία Βάσης Δεδομένων")
        card = self._card(f)
        self._label(card, "Κωδικός Βιβλίου (π.χ. AN01):")
        tk.Entry(
            card,
            textvariable=self.dv["code"],
            font=("Arial", 12),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
            width=20,
        ).pack(anchor="w", pady=3)
        self._label(card, "Bunny Base URL (π.χ. https://fanari.b-cdn.net):")
        tk.Entry(
            card,
            textvariable=self.dv["bunny"],
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        ).pack(fill="x", pady=3)
        self._label(card, "Φάκελος MP3 (προαιρετικό — αφήστε κενό για φάκελο εργασίας):")
        row_mp3 = tk.Frame(card, bg=WHITE)
        row_mp3.pack(fill="x", pady=3)
        tk.Entry(
            row_mp3,
            textvariable=self.dv["mp3_fold"],
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        ).pack(side="left", fill="x", expand=True)
        _btn(row_mp3, "Αναζήτηση…", self._browse_mp3_folder, width=14).pack(
            side="right", padx=(6, 0)
        )
        # MP3 tools: validate + rename/copy
        row_mp3_btns = tk.Frame(card, bg=WHITE)
        row_mp3_btns.pack(fill="x", pady=3)
        _btn(
            row_mp3_btns,
            "🔊  Έλεγχος MP3",
            self._validate_mp3,
            bg=GREEN,
            width=18,
        ).pack(side="left", padx=(0, 6))
        _btn(
            row_mp3_btns,
            "Μετονομασία MP3",
            self.rename_mp3,
            bg=MID_RED,
            width=18,
        ).pack(side="left")
        tk.Frame(card, bg=GREY_MED, height=1).pack(fill="x", pady=12)
        _btn(
            card,
            "📊  Δημιουργία database.xlsx",
            self._gen_db,
            big=True,
        ).pack(fill="x", pady=6)
        self.dbprev = tk.Text(
            card,
            font=("Courier", 9),
            bg=GREY_LIGHT,
            fg=TEXT_DARK,
            height=14,
            relief="flat",
            state="disabled",
        )
        self.dbprev.pack(fill="both", expand=True, pady=6)

    def _build_tab5(self):
        f = self.tab5
        self._section_header(f, "🎵  5. Αντιστοίχιση Ύμνων")
        card = self._card(f)
        tk.Label(
            card,
            text="Ορίστε τον τίτλο και προαιρετικά Ήχο/Τμήμα. MP3 Code, File και URL δημιουργούνται αυτόματα.",
            bg=WHITE,
            fg=TEXT_DARK,
            font=("Arial", 9),
        ).pack(anchor="w", pady=(0, 6))
        _btn(card, "🔄  Ανανέωση", self._refresh_tab5).pack(anchor="w", pady=4)
        # Scrollable area (song buttons / rows)
        canvas_frame = tk.Frame(card, bg=WHITE)
        canvas_frame.pack(fill="both", expand=True, pady=6)
        self.assign_canvas = tk.Canvas(canvas_frame, bg=WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.assign_canvas.yview)
        self.assign_inner = tk.Frame(self.assign_canvas, bg=WHITE)
        self.assign_inner.bind(
            "<Configure>",
            lambda e: self.assign_canvas.configure(scrollregion=self.assign_canvas.bbox("all")),
        )
        self.assign_canvas.create_window((0, 0), window=self.assign_inner, anchor="nw")
        self.assign_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.assign_canvas.pack(side="left", fill="both", expand=True)
        # Hymn preview panel (below song buttons)
        preview_frame = tk.Frame(card, bg=LIGHT_RED, bd=1, relief="solid")
        preview_frame.pack(fill="x", pady=(8, 4))
        tk.Label(
            preview_frame,
            text="Προεπισκόπηση ύμνου",
            bg=LIGHT_RED,
            fg=DARK_RED,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", padx=8, pady=(6, 2))
        # Content row: large thumbnail on left, hymn code + first 1–2 lines on right
        preview_content = tk.Frame(preview_frame, bg=LIGHT_RED)
        preview_content.pack(fill="x", padx=8, pady=(0, 8))
        # Left: large clickable thumbnail
        thumbnail_frame = tk.Frame(preview_content, bg=GREY_LIGHT, bd=1, relief="solid", cursor="hand2")
        thumbnail_frame.pack(side="left", padx=(0, 12), pady=0)
        self.preview_thumbnail_lbl = tk.Label(
            thumbnail_frame,
            text="Κάντε κλικ σε γραμμή",
            bg=GREY_LIGHT,
            fg=TEXT_DARK,
            font=("Arial", 9),
            cursor="hand2",
            anchor="center",
        )
        self.preview_thumbnail_lbl.pack(padx=6, pady=6)
        self.preview_thumbnail_lbl.bind("<Button-1>", lambda e: self._open_preview_pdf())
        thumbnail_frame.bind("<Button-1>", lambda e: self._open_preview_pdf())
        self._preview_photo = None
        self._preview_pdf_path = ""
        self._preview_page = 0
        # Right: hymn code + first 1–2 lines (horizontal text)
        right_frame = tk.Frame(preview_content, bg=LIGHT_RED)
        right_frame.pack(side="left", fill="both", expand=True)
        self.preview_code_lbl = tk.Label(
            right_frame,
            text="—",
            bg=LIGHT_RED,
            fg=DARK_RED,
            font=("Arial", 12, "bold"),
            anchor="w",
        )
        self.preview_code_lbl.pack(anchor="w", pady=(0, 4))
        self.preview_text = tk.Text(
            right_frame,
            wrap="word",
            height=3,
            font=("Arial", 10),
            bg=LIGHT_RED,
            fg=TEXT_DARK,
            relief="flat",
            state="disabled",
        )
        self.preview_text.pack(anchor="w", fill="x", expand=True)
        self.preview_text.config(state="normal")
        self.preview_text.insert("1.0", "Κάντε κλικ σε μια γραμμή για να δείτε την αρχή του ύμνου.")
        self.preview_text.config(state="disabled")
        self._tab5_preview_row_index = -1

    def _on_tab_changed(self, event):
        """Refresh Tab 5 when selected."""
        try:
            nb = event.widget
            if nb.index(nb.select()) == 4:  # tab 5
                self._refresh_tab5()
        except Exception:
            pass

    def _init_assignments(self):
        """Reset assignments to match current markers (call after detect)."""
        self.assignments = []
        ordered = sorted(self.mrks, key=lambda m: (m.page, m.y))
        for _ in ordered:
            self.assignments.append({
                "song_title": tk.StringVar(),
                "echos": tk.StringVar(),
                "section": tk.StringVar(),
            })

    def _refresh_tab5(self):
        """Rebuild assignment rows (preserves edits)."""
        for w in self.assign_inner.winfo_children():
            w.destroy()
        if not self.mrks:
            tk.Label(
                self.assign_inner,
                text="Εκτελέστε «Εντοπισμός Markers» στο Tab 2.",
                bg=WHITE,
                fg=TEXT_DARK,
                font=("Arial", 10),
            ).pack(pady=20)
            return
        if len(self.assignments) != len(self.mrks):
            self._init_assignments()
        code = (self.dv["code"].get() or "").strip() or "BOOK"
        bunny = (self.dv["bunny"].get() or "").strip() or DEFAULT_BUNNY_BASE_URL
        pdf = self.pdf_path.get().strip()
        ordered = sorted(self.mrks, key=lambda m: (m.page, m.y))
        for i, m in enumerate(ordered):
            preview = extract_preview_text(pdf, m) if pdf and os.path.isfile(pdf) else ""
            row = tk.Frame(self.assign_inner, bg=GREY_LIGHT, relief="flat", bd=0, cursor="hand2")
            row.pack(fill="x", pady=1)
            row.bind("<Button-1>", lambda e, idx=i: self._on_preview_row(idx))
            tk.Label(row, text=f"#{i+1:03d}", width=5, bg=GREY_LIGHT, font=("Courier", 9)).pack(side="left", padx=2, pady=2)
            tk.Label(row, text=f"Σελ {m.page}", width=5, bg=GREY_LIGHT, font=("Courier", 9)).pack(side="left", padx=2, pady=2)
            tk.Label(row, text=f"Y{m.y:.0f}", width=5, bg=GREY_LIGHT, font=("Courier", 9)).pack(side="left", padx=2, pady=2)
            tk.Label(
                row,
                text=preview or "—",
                width=32,
                wraplength=280,
                bg=GREY_LIGHT,
                fg=TEXT_DARK,
                font=("Arial", 8),
                anchor="w",
                justify="left",
            ).pack(side="left", padx=2, pady=2)
            e_title = tk.Entry(row, textvariable=self.assignments[i]["song_title"], width=28, font=("Arial", 9))
            e_title.pack(side="left", padx=2, pady=2)
            _enable_clipboard_paste(self.root, e_title)
            e_echos = tk.Entry(row, textvariable=self.assignments[i]["echos"], width=8, font=("Arial", 9))
            e_echos.pack(side="left", padx=2, pady=2)
            _enable_clipboard_paste(self.root, e_echos)
            e_section = tk.Entry(row, textvariable=self.assignments[i]["section"], width=10, font=("Arial", 9))
            e_section.pack(side="left", padx=2, pady=2)
            _enable_clipboard_paste(self.root, e_section)
            mp3_code = get_mp3_code(code, i + 1)
            tk.Label(row, text=mp3_code, width=10, bg=GREY_LIGHT, fg=TEXT_DARK, font=("Courier", 9)).pack(side="left", padx=2, pady=2)
            tk.Label(row, text=get_mp3_file(code, i + 1), width=14, bg=GREY_LIGHT, fg=TEXT_DARK, font=("Courier", 9)).pack(side="left", padx=2, pady=2)
            url = get_mp3_url(bunny, code, i + 1)
            url_short = (url[:45] + "…") if len(url) > 48 else url
            url_lbl = tk.Label(row, text=url_short, width=48, bg=GREY_LIGHT, fg=TEXT_DARK, font=("Courier", 8), anchor="w")
            url_lbl.pack(side="left", padx=2, pady=2, fill="x", expand=True)
            for w in row.winfo_children():
                if isinstance(w, (tk.Label, tk.Entry)):
                    w.bind("<Button-1>", lambda e, idx=i: self._on_preview_row(idx))
        self._s("Ανανέωση Αντιστοίχισης")

    def _on_preview_row(self, row_index: int):
        """Update hymn preview panel when user clicks a song row."""
        if not self.mrks or row_index < 0:
            return
        ordered = sorted(self.mrks, key=lambda m: (m.page, m.y))
        if row_index >= len(ordered):
            return
        m = ordered[row_index]
        # Use actual page from marker (1-based PDF page); never default to 1
        page_number = m.page
        if page_number < 1:
            page_number = 0
        hymn_code = f"#{row_index + 1:03d}"
        title = (self.assignments[row_index]["song_title"].get() or "").strip()
        display_code = f"{hymn_code}  {title}" if title else hymn_code
        self.preview_code_lbl.config(text=display_code)
        pdf = self.pdf_path.get().strip()
        self._preview_pdf_path = pdf
        self._preview_page = page_number
        self._tab5_preview_row_index = row_index
        # First 1–2 lines of hymn text
        if pdf and os.path.isfile(pdf):
            content = extract_hymn_preview_lines(pdf, m, max_lines=2, max_chars_per_line=90)
            content = content if content else "Preview unavailable for this piece."
        else:
            content = "Preview unavailable for this piece."
        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", content)
        self.preview_text.config(state="disabled")
        # Debug: verify page before rendering (remove after fixing)
        if pdf:
            short_pdf = os.path.basename(pdf)
            print(f"Preview row={hymn_code} page={page_number} pdf={short_pdf}")
        self._update_preview_thumbnail(pdf, page_number)

    def _update_preview_thumbnail(self, pdf_path: str, page_number: int):
        """Render and display PDF page thumbnail; show placeholder on failure."""
        if not pdf_path or not os.path.isfile(pdf_path):
            self.preview_thumbnail_lbl.config(image="", text="Thumbnail\nunavailable", compound="center")
            self._preview_photo = None
            return
        if not ImageTk:
            self.preview_thumbnail_lbl.config(image="", text="Thumbnail\nunavailable", compound="center")
            self._preview_photo = None
            return
        if page_number < 1:
            self.preview_thumbnail_lbl.config(image="", text="Thumbnail\nunavailable", compound="center")
            self._preview_photo = None
            return
        img = render_page_thumbnail(pdf_path, page_number, max_width=230)
        if img is None:
            self.preview_thumbnail_lbl.config(image="", text="Thumbnail\nunavailable", compound="center")
            self._preview_photo = None
            return
        photo = ImageTk.PhotoImage(img)
        self._preview_photo = photo
        self.preview_thumbnail_lbl.config(image=photo, text="", compound="image")
        self.preview_thumbnail_lbl.image = photo

    def _find_acrobat_reader(self) -> str | None:
        """Find Adobe Acrobat Reader on Windows. Returns exe path or None."""
        if sys.platform != "win32":
            return None
        common_paths = [
            os.path.join(os.environ.get("ProgramFiles", ""), "Adobe", "Acrobat DC", "Acrobat", "Acrobat.exe"),
            os.path.join(os.environ.get("ProgramFiles", ""), "Adobe", "Acrobat Reader DC", "Reader", "AcroRd64.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Adobe", "Acrobat Reader DC", "Reader", "AcroRd32.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Adobe", "Acrobat Reader 2023", "Reader", "AcroRd32.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Adobe", "Acrobat Reader 2017", "Reader", "AcroRd32.exe"),
        ]
        for p in common_paths:
            if p and os.path.isfile(p):
                return p
        return None

    def _open_preview_pdf(self):
        """Open the selected PDF at the correct page if possible.

        Note: os.startfile() always opens page 1 because the default Windows PDF
        viewer (Edge or built-in) ignores the #page=N fragment in the path.
        We try Adobe Acrobat Reader with /A "page=N" when available.
        """
        path = self._preview_pdf_path or self.pdf_path.get().strip()
        if not path or not os.path.isfile(path):
            self._s("Δεν υπάρχει PDF για άνοιγμα.")
            return
        path = os.path.normpath(path)
        page = self._preview_page or 0
        print(f"Open PDF path={path} page={page}")

        try:
            if sys.platform == "win32":
                acrobat = self._find_acrobat_reader()
                if acrobat and page > 1:
                    subprocess.Popen([acrobat, "/A", f"page={page}", path])
                    self._s(f"Άνοιγμα σελ. {page}: {os.path.basename(path)}")
                else:
                    os.startfile(path)
                    self._s(f"Άνοιγμα: {os.path.basename(path)}")
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.run([opener, path], check=False)
                self._s(f"Άνοιγμα: {os.path.basename(path)}")
        except (OSError, FileNotFoundError) as e:
            self._s(f"Σφάλμα άνοιγματος: {e}")

    def _browse_folder(self):
        d = filedialog.askdirectory(title="Επιλογή φακέλου βιβλίου")
        if d:
            self.fold.set(d)
            self._s(f"Φάκελος: {d}")

    def _browse_pdf(self):
        p = filedialog.askopenfilename(
            title="Επιλογή PDF",
            filetypes=[("PDF αρχεία", "*.pdf"), ("Όλα τα αρχεία", "*.*")],
        )
        if p:
            self.pdf_path.set(p)
            if not self.fold.get():
                self.fold.set(os.path.dirname(p))
            self._s(f"PDF: {os.path.basename(p)}")

    def _browse_mp3_folder(self):
        d = filedialog.askdirectory(title="Επιλογή φακέλου MP3 για το τρέχον βιβλίο")
        if d:
            self.dv["mp3_fold"].set(d)
            self._s(f"Φάκελος MP3: {d}")

    def _detect(self):
        pdf = self.pdf_path.get().strip()
        if not pdf or not os.path.isfile(pdf):
            messagebox.showerror("Σφάλμα", "Επιλέξτε έγκυρο PDF (Tab 1).")
            return
        self._s("🔍 Αναζήτηση markers…")
        self.mrks = detect_markers(pdf)
        self._init_assignments()
        n = len(self.mrks)
        self.cnt_lbl.config(
            text=f"✅ Βρέθηκαν {n} markers ■" if n else "⚠️ Δεν βρέθηκαν markers ■",
            fg=GREEN if n else "orange",
        )
        self._refresh_list()
        self._s(f"Βρέθηκαν {n} markers.")

    def _apply(self):
        pdf = self.pdf_path.get().strip()
        if not pdf:
            messagebox.showerror("Σφάλμα", "Επιλέξτε PDF (Tab 1).")
            return
        if not self.mrks:
            messagebox.showerror(
                "Σφάλμα", "Εκτελέστε πρώτα «Εντοπισμός Markers»."
            )
            return
        folder = self.fold.get().strip() or os.path.dirname(pdf)
        base = os.path.splitext(os.path.basename(pdf))[0]
        out = os.path.join(folder, base + "_με_κουμπιά.pdf")
        self.prog["value"] = 0

        def run():
            def cb(done: int, total: int):
                pct = int(done / total * 100)
                self.prog["value"] = pct
                self.prog_lbl.config(text=f"{done}/{total} κουμπιά")
                self.root.update_idletasks()

            n = apply_markers(pdf, self.mrks, out, progress_cb=cb)
            # Show messagebox on main thread
            self.root.after(
                0,
                lambda: self._on_apply_done(out, n),
            )

        threading.Thread(target=run, daemon=True).start()

    def _on_apply_done(self, out_path: str, count: int):
        self._s(f"✅ Αποθηκεύτηκε: {out_path}  ({count} κουμπιά)")
        messagebox.showinfo(
            "Έτοιμο!",
            f"✅ PDF με κουμπιά:\n{out_path}\n\n{count} κουμπιά τοποθετήθηκαν.",
        )

    def _refresh_list(self):
        self.lst.delete(0, "end")
        for i, m in enumerate(self.mrks):
            state = "✅" if m.keep else "⛔"
            self.lst.insert(
                "end",
                f"  {state}  #{i + 1:03d}   Σελ {m.page:3d}   Y={m.y:.0f}",
            )

    def _toggle_keep(self):
        sel = self.lst.curselection()
        if not sel:
            messagebox.showinfo(
                "Πληροφορία", "Επιλέξτε ένα στοιχείο από τη λίστα."
            )
            return
        idx = sel[0]
        self.mrks[idx].keep = not self.mrks[idx].keep
        self._refresh_list()
        self.lst.selection_set(idx)

    def _validate_mp3(self):
        """Validate that expected BOOKCODE-NNN.mp3 exist in MP3 folder (current book)."""
        if not self.mrks:
            messagebox.showinfo(
                "Πληροφορία",
                "Εκτελέστε πρώτα «Εντοπισμός Markers» (Tab 2).",
            )
            return
        code = (self.dv["code"].get() or "").strip()
        if not code:
            messagebox.showwarning(
                "Κωδικός Βιβλίου",
                "Εισάγετε Κωδικό Βιβλίου (π.χ. AN01) για έλεγχο MP3.",
            )
            return
        mp3_folder = (self.dv["mp3_fold"].get() or "").strip() or self.fold.get().strip()
        if not mp3_folder or not os.path.isdir(mp3_folder):
            messagebox.showwarning(
                "Φάκελος MP3",
                "Επιλέξτε φάκελο εργασίας (Tab 1) ή φάκελο MP3 για τον έλεγχο.",
            )
            return
        ok, missing = validate_missing_mp3(mp3_folder, self.mrks, code)
        if ok:
            self._s("✅ Όλα τα MP3 υπάρχουν")
            messagebox.showinfo("Έλεγχος MP3", "Όλα τα αναμενόμενα αρχεία MP3 βρέθηκαν.")
        else:
            self._s("⚠️ Λείπουν αρχεία MP3")
            # Offer automatic rename/copy when expected files are missing
            msg = (
                "Δεν βρέθηκαν όλα τα αναμενόμενα αρχεία MP3 "
                f"για τον κωδικό βιβλίου {code}.\n\n"
                "Θέλετε να γίνει αυτόματη μετονομασία ή αντιγραφή "
                "των αρχείων σε μορφή BOOKCODE-###.mp3;"
            )
            if messagebox.askyesno("Λείπουν αρχεία MP3", msg):
                # Let the dedicated tool handle preview, confirmation and processing
                self.rename_mp3()
            else:
                messagebox.showwarning(
                    "Λείπουν αρχεία MP3",
                    "Δεν βρέθηκαν τα ακόλουθα αρχεία:\n\n"
                    + "\n".join(missing[:25])
                    + ("\n…" if len(missing) > 25 else ""),
                )

    def rename_mp3(self):
        """Rename or copy MP3 files to BOOKCODE-###.mp3 in a selected folder."""
        code = (self.dv["code"].get() or "").strip()
        if not code:
            messagebox.showerror(
                "Κωδικός Βιβλίου",
                "Ο Κωδικός Βιβλίου είναι υποχρεωτικός (π.χ. AN01) για τη μετονομασία MP3.",
            )
            return
        # Choose MP3 folder (default to existing MP3 folder or working folder)
        initial = (self.dv["mp3_fold"].get() or "").strip() or self.fold.get().strip()
        folder = filedialog.askdirectory(
            title="Επιλογή φακέλου MP3 για μετονομασία", initialdir=initial or None
        )
        if not folder:
            return
        self.dv["mp3_fold"].set(folder)
        self._s(f"Φάκελος MP3: {folder}")
        try:
            names = os.listdir(folder)
        except OSError as exc:
            messagebox.showerror("Σφάλμα", f"Δεν ήταν δυνατή η ανάγνωση φακέλου MP3:\n{exc}")
            return
        mp3_files = [n for n in names if n.lower().endswith(".mp3")]
        if not mp3_files:
            messagebox.showinfo("Πληροφορία", "Δεν βρέθηκαν αρχεία MP3 σε αυτόν τον φάκελο.")
            return
        mp3_files.sort()
        if len(mp3_files) > 999:
            messagebox.showerror(
                "Πάρα πολλά αρχεία",
                "Υποστηρίζονται μέχρι 999 αρχεία MP3 (BOOKCODE-001 έως BOOKCODE-999).",
            )
            return
        mappings = []
        already_ok = 0
        conflicts = []
        code_clean = code.strip()
        for idx, name in enumerate(mp3_files, start=1):
            new_base = f"{code_clean}-{idx:03d}.mp3"
            old_path = os.path.join(folder, name)
            new_path = os.path.join(folder, new_base)
            if name.lower() == new_base.lower():
                already_ok += 1
                continue
            if os.path.exists(new_path) and os.path.normcase(new_path) != os.path.normcase(old_path):
                conflicts.append((name, new_base))
                continue
            mappings.append((old_path, new_path, name, new_base))
        if not mappings and not conflicts:
            messagebox.showinfo(
                "Μετονομασία MP3",
                "Όλα τα αρχεία MP3 είναι ήδη στη σωστή μορφή BOOKCODE-###.mp3.",
            )
            self._validate_mp3()
            return
        # Build preview text
        lines = [f"{old}  →  {new}" for (_, _, old, new) in mappings]
        preview = "\n".join(lines[:30])
        if len(lines) > 30:
            preview += f"\n… ({len(lines) - 30} ακόμη αντιστοιχίσεις)"
        if conflicts:
            preview += "\n\nΠροειδοποίηση: Τα παρακάτω δεν θα αλλάξουν λόγω σύγκρουσης ονομάτων:\n"
            preview += "\n".join(f"{o}  ⇢  {n}" for (o, n) in conflicts[:20])
            if len(conflicts) > 20:
                preview += f"\n… ({len(conflicts) - 20} ακόμη συγκρούσεις)"
        # Ask for COPY (default, safer)
        msg = (
            f"Κωδικός Βιβλίου: {code_clean}\n"
            f"Φάκελος: {folder}\n\n"
            "Προεπισκόπηση μετονομασιών (παλιό → νέο):\n\n"
            f"{preview}\n\n"
            "Προτείνεται ΛΕΙΤΟΥΡΓΙΑ ΑΝΤΙΓΡΑΦΗΣ (δεν τροποποιεί τα αρχικά αρχεία).\n\n"
            "Θέλετε να συνεχίσετε με ΑΝΤΙΓΡΑΦΗ;"
        )
        do_copy = messagebox.askyesno("Μετονομασία MP3", msg)
        mode = "copy" if do_copy else "rename"
        if not do_copy:
            if not messagebox.askyesno(
                "Μετονομασία MP3",
                "Θέλετε να συνεχίσετε με ΜΕΤΟΝΟΜΑΣΙΑ των αρχικών αρχείων;",
            ):
                return
        processed = 0
        errors = 0
        for old_path, new_path, _, _ in mappings:
            try:
                if mode == "copy":
                    if os.path.exists(new_path) and os.path.normcase(new_path) != os.path.normcase(old_path):
                        continue
                    shutil.copy2(old_path, new_path)
                else:
                    if os.path.exists(new_path) and os.path.normcase(new_path) != os.path.normcase(old_path):
                        continue
                    os.rename(old_path, new_path)
                processed += 1
            except Exception:
                errors += 1
        skipped = already_ok + len(conflicts)
        summary = (
            f"Σύνολο αρχείων MP3: {len(mp3_files)}\n"
            f"Επεξεργάστηκαν ({'αντιγράφηκαν' if mode=='copy' else 'μετονομάστηκαν'}): {processed}\n"
            f"Παραλείφθηκαν (ήδη σωστά / συγκρούσεις): {skipped}\n"
            f"Σφάλματα: {errors}"
        )
        messagebox.showinfo("Μετονομασία MP3", summary)
        # Re-run validation using the updated folder
        self._validate_mp3()

    def _gen_db(self):
        if not self.mrks:
            messagebox.showerror(
                "Σφάλμα",
                "Εκτελέστε πρώτα «Εντοπισμός Markers» (Tab 2).",
            )
            return
        fo = self.fold.get().strip()
        if not fo:
            messagebox.showerror("Σφάλμα", "Επιλέξτε φάκελο (Tab 1).")
            return
        code = (self.dv["code"].get() or "").strip()
        if not code:
            messagebox.showerror(
                "Σφάλμα",
                "Ο Κωδικός Βιβλίου είναι υποχρεωτικός (π.χ. AN01).",
            )
            return
        ok, msg = validate_empty_book_code(code)
        if not ok:
            messagebox.showerror("Σφάλμα", msg)
            return
        ok, msg = validate_duplicate_positions(self.mrks)
        if not ok:
            messagebox.showwarning("Προειδοποίηση", msg + "\n\nΜπορείτε να συνεχίσετε ή να διορθώσετε στη λίστα (Tab 3).")
        ok, msg = validate_page_numbers(self.mrks)
        if not ok:
            messagebox.showerror("Σφάλμα", msg)
            return
        bunny = (self.dv["bunny"].get() or "").strip() or DEFAULT_BUNNY_BASE_URL
        ordered = sorted(self.mrks, key=lambda m: (m.page, m.y))
        assignments_data = []
        for i in range(len(ordered)):
            a = self.assignments[i] if i < len(self.assignments) else {}
            sv = lambda v: (v.get() if hasattr(v, "get") else (v or ""))
            song_title = (sv(a.get("song_title", "")) or "").strip()
            echos = (sv(a.get("echos", "")) or "").strip()
            section = (sv(a.get("section", "")) or "").strip()
            assignments_data.append({
                "song_title": song_title,
                "echos": echos,
                "section": section,
                "status": "TODO",
                "notes": "",
            })

        path, count = build_database_xlsx(
            fo, self.mrks, code=code, bunny_base_url=bunny, assignments=assignments_data
        )
        self._s(f"✅ {path}")
        messagebox.showinfo(
            "Έτοιμο!",
            f"✅ Βάση δεδομένων:\n{path}\n\nΕγγραφές: {count}",
        )
        mp3_folder = (self.dv["mp3_fold"].get() or "").strip() or fo
        ok_mp3, missing = validate_missing_mp3(mp3_folder, self.mrks, code)
        if not ok_mp3 and missing:
            self._s("⚠️ Λείπουν αρχεία MP3")
            messagebox.showwarning(
                "Λείπουν αρχεία MP3",
                "Ο φάκελος δεν περιέχει τα ακόλουθα αρχεία:\n\n"
                + "\n".join(missing[:20])
                + ("\n…" if len(missing) > 20 else ""),
            )
        lines = preview_lines(self.mrks, code=code, bunny_base_url=bunny)
        self.dbprev.config(state="normal")
        self.dbprev.delete("1.0", "end")
        self.dbprev.insert("end", "\n".join(lines))
        self.dbprev.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
