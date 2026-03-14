# -*- coding: utf-8 -*-
"""ToFanari — Main GUI application."""

import csv
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Tuple
from urllib.parse import quote


def _get_app_base_path() -> str:
    """Return a base path safe for packaged (frozen) execution. Use for any app-bundled resources."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


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
)
from validation_preflight import (
    run_full_validation,
    validate_mp3_numbering,
    validate_mp3_filename_pattern,
)
from book_registry import (
    load_book_registry,
    find_book_for_chapter,
    append_book_to_registry,
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


def _clean_preview_for_title(preview: str) -> str:
    """Clean extracted preview text for use as hymn title: remove bullets/symbols, normalize spaces."""
    if not preview or not isinstance(preview, str):
        return ""
    s = preview.strip()
    for ch in "\u25a0\u25aa\u2022\u00b7\u2023\u2043\u2219\u2024\u2027\u2022\u2024":
        s = s.replace(ch, " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:200] if len(s) > 200 else s


def song_title_from_mp3_file(mp3_file: str) -> str:
    """Return MP3 filename without .mp3 extension. No cleaning or transformation."""
    if not mp3_file:
        return ""
    return os.path.splitext(os.path.basename(mp3_file))[0]


def is_internal_generated_mp3(filename: str, book_code: str) -> bool:
    """
    True only if filename matches BOOKCODE-NNN.mp3 (already-generated internal format).
    Excludes: AN01-001.mp3, BOOK-001.mp3, <BOOKCODE>-<number>.mp3
    Includes: 001 Title.mp3, 010 Another.mp3 (source files)
    """
    if not filename or not (book_code or "").strip():
        return False
    code = (book_code or "").strip()
    # Must match: BOOKCODE- then digits only, then .mp3 (case-insensitive)
    pattern = rf"^{re.escape(code)}-\d+\.mp3$"
    return re.match(pattern, filename, re.IGNORECASE) is not None


def split_mp3_files(mp3_folder: str, book_code: str) -> tuple[List[str], List[str]]:
    """
    Split MP3 files in folder into source and generated.
    Mixed folders (source + generated) are supported and expected.
    Returns: (source_files, generated_files)
    - source_files: original files (001 Title.mp3, etc.)
    - generated_files: app-created BOOKCODE-NNN.mp3
    """
    source_files: List[str] = []
    generated_files: List[str] = []
    if not mp3_folder or not os.path.isdir(mp3_folder):
        return (source_files, generated_files)
    code = (book_code or "").strip()
    try:
        for f in os.listdir(mp3_folder):
            full = os.path.join(mp3_folder, f)
            if not os.path.isfile(full):
                continue
            if not f.lower().endswith(".mp3"):
                continue
            if is_internal_generated_mp3(f, code):
                generated_files.append(f)
            else:
                source_files.append(f)
    except OSError:
        pass
    return (sorted(source_files), sorted(generated_files))


def get_source_mp3_files(mp3_folder: str, book_code: str) -> List[str]:
    """Return source MP3 files (convenience wrapper around split_mp3_files for mixed folder)."""
    source, _ = split_mp3_files(mp3_folder, book_code)
    return source


def list_mp3_files_in_folder(folder: str) -> List[str]:
    """List all .mp3 files in folder (case-insensitive). For source folder, all are source files."""
    if not folder or not os.path.isdir(folder):
        return []
    try:
        return sorted(
            f for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(".mp3")
        )
    except OSError:
        return []


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

        self.pdf_path = tk.StringVar()  # Original PDF (selected in Step 1)
        self.marked_pdf_path = tk.StringVar()  # Marked PDF (created in Step 2)
        self.original_pdf_path = ""  # Selected PDF path (set by _pick_pdf)
        self.work_folder = ""  # dirname(original_pdf_path), computed after PDF selection
        self.status = tk.StringVar(value=f"Καλωσήρθατε στο {APP_TITLE} {VERSION}")
        self.mrks: List[Marker] = []
        self.assignments: List[dict] = []  # one per marker: song_title, echos, section (StringVars)
        # Mapping from internal MP3 filename (e.g. AN01-001.mp3) to original source name
        # e.g. "AN01-001.mp3" -> "001 Κύριε Ἐκέκραξα.mp3"
        self.mp3_original_name_by_new_file: dict[str, str] = {}

        self.source_mp3_folder = ""  # Exact path selected by user; never append input_mp3/mp3
        self.dv = {
            "code": tk.StringVar(value="BOOK"),
            "bunny": tk.StringVar(value=DEFAULT_BUNNY_BASE_URL),
            "mp3_folder": tk.StringVar(),  # Mirrors source_mp3_folder for UI
        }
        self.bunny_prep = {
            "base_cdn_url": tk.StringVar(value=DEFAULT_BUNNY_BASE_URL),
            "root_remote_folder": tk.StringVar(value="books"),
            "book_slug": tk.StringVar(),
            "chapter_code": tk.StringVar(),
            "thinkific_course_name": tk.StringVar(),
            "thinkific_chapter_name": tk.StringVar(),
            "flipbuilder_book_name": tk.StringVar(),
            "api_key": tk.StringVar(),
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
        self.tab6 = tk.Frame(nb, bg=CREAM)
        self.tab7 = tk.Frame(nb, bg=CREAM)
        self.tab8 = tk.Frame(nb, bg=CREAM)
        nb.add(self.tab1, text="  1. Επιλογή Βιβλίου  ")
        nb.add(self.tab2, text="  2. Σήμανση PDF  ")
        nb.add(self.tab3, text="  3. Έλεγχος Κουμπιών  ")
        nb.add(self.tab4, text="  4. Βάση Δεδομένων  ")
        nb.add(self.tab5, text="  5. Αντιστοίχιση Ύμνων  ")
        nb.add(self.tab6, text="  6. Έλεγχος Βάσης  ")
        nb.add(self.tab7, text="  7. Bunny.net Preparation  ")
        nb.add(self.tab8, text="  8. Book Registry  ")
        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self.book_registry_books: List[dict] = []
        self.book_registry_path: str = ""
        self.book_registry_add_vars: dict = {}

        self._build_tab1()
        self._build_tab2()
        self._build_tab3()
        self._build_tab4()
        self._build_tab5()
        self._build_tab6()
        self._build_tab7()
        self._build_tab8()

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

    def get_mp3_folder(self) -> str:
        """MP3 folder selected in Tab 4. Returns exact path—never modified or appended."""
        return (self.source_mp3_folder or "").strip()

    def get_current_mp3_files(self) -> List[str]:
        """
        Return sorted list of MP3 filenames in the active MP3 folder only.
        Uses os.listdir(mp3_folder) only — no recursive, no subfolders, no cache.
        Excludes directories via os.path.isfile.
        """
        mp3_folder = self.get_mp3_folder()
        if not mp3_folder or not os.path.isdir(mp3_folder):
            return []
        try:
            return sorted(
                f for f in os.listdir(mp3_folder)
                if os.path.isfile(os.path.join(mp3_folder, f)) and f.lower().endswith(".mp3")
            )
        except OSError:
            return []

    def reset_mp3_runtime_state(self) -> None:
        """
        Clear MP3-related runtime state. Call at start of Έλεγχος MP3 and Validate Database.
        """
        self.mp3_original_name_by_new_file.clear()
        if hasattr(self, "validation_report_text") and self.validation_report_text.winfo_exists():
            try:
                self.validation_report_text.config(state="normal")
                self.validation_report_text.delete("1.0", tk.END)
                self.validation_report_text.insert("1.0", "Εκτελέστε «Έλεγχος Βάσης» για νέα αναφορά.")
                self.validation_report_text.config(state="disabled")
            except tk.TclError:
                pass

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
        self._section_header(f, "📚  Επιλογή Βιβλίου")
        card = self._card(f)

        self._label(card, "Original PDF / Αρχείο PDF πρωτότυπο:")
        row = tk.Frame(card, bg=WHITE)
        row.pack(fill="x", pady=3)
        tk.Entry(
            row,
            textvariable=self.pdf_path,
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        ).pack(side="left", fill="x", expand=True)
        _btn(
            row,
            "Νέο Βιβλίο / Reset",
            self._confirm_reset_project,
            bg=MID_RED,
            width=18,
        ).pack(side="right", padx=(6, 4))
        _btn(row, "Επιλογή PDF…", self._pick_pdf, width=14).pack(side="right", padx=(6, 0))

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

    def _confirm_reset_project(self):
        """Ask confirmation then reset project state."""
        if messagebox.askyesno(
            "Νέο Βιβλίο / Reset",
            "Do you want to clear the current project and start a new one?",
        ):
            self.reset_project_state()

    def reset_project_state(self):
        """Clear all current project state; app behaves like a fresh launch. Does not close the app."""
        self.pdf_path.set("")
        self.marked_pdf_path.set("")
        self.original_pdf_path = ""
        self.work_folder = ""
        self.source_mp3_folder = ""
        self.dv["mp3_folder"].set("")
        self.dv["code"].set("BOOK")
        self.dv["bunny"].set(DEFAULT_BUNNY_BASE_URL)
        self.mrks = []
        self.assignments = []
        self.mp3_original_name_by_new_file.clear()
        self.status.set(f"Καλωσήρθατε στο {APP_TITLE} {VERSION}")
        if hasattr(self, "tab2_original_pdf_lbl") and self.tab2_original_pdf_lbl.winfo_exists():
            self.tab2_original_pdf_lbl.config(text="—")
        if hasattr(self, "tab2_marked_pdf_lbl") and self.tab2_marked_pdf_lbl.winfo_exists():
            self.tab2_marked_pdf_lbl.config(text="—")
        if hasattr(self, "cnt_lbl") and self.cnt_lbl.winfo_exists():
            self.cnt_lbl.config(text="—", fg=TEXT_DARK)
        if hasattr(self, "lst") and self.lst.winfo_exists():
            self.lst.delete(0, "end")
        if hasattr(self, "mp3_files_count_lbl") and self.mp3_files_count_lbl.winfo_exists():
            self.mp3_files_count_lbl.config(text="MP3 Files Found: 0")
        if hasattr(self, "mp3_validation_report") and self.mp3_validation_report.winfo_exists():
            self.mp3_validation_report.config(state="normal")
            self.mp3_validation_report.delete("1.0", tk.END)
            self.mp3_validation_report.insert("1.0", "Επιλέξτε φάκελο MP3 και πατήστε «Έλεγχος MP3» για αναφορά.")
            self.mp3_validation_report.config(state="disabled")
        if hasattr(self, "btn_validate_mp3") and self.btn_validate_mp3.winfo_exists():
            self.btn_validate_mp3.config(state="disabled")
        if hasattr(self, "btn_gen_db") and self.btn_gen_db.winfo_exists():
            self.btn_gen_db.config(state="disabled")
        if hasattr(self, "assign_inner") and self.assign_inner.winfo_exists():
            for w in self.assign_inner.winfo_children():
                w.destroy()
            tk.Label(
                self.assign_inner,
                text="Εκτελέστε «Εντοπισμός Markers» στο Tab 2.",
                bg=WHITE,
                fg=TEXT_DARK,
                font=("Arial", 10),
            ).pack(pady=20)
        if hasattr(self, "preview_code_lbl") and self.preview_code_lbl.winfo_exists():
            self.preview_code_lbl.config(text="—")
        if hasattr(self, "preview_text") and self.preview_text.winfo_exists():
            self.preview_text.config(state="normal")
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert("1.0", "Κάντε κλικ σε μια γραμμή για να δείτε την αρχή του ύμνου.")
            self.preview_text.config(state="disabled")
        if hasattr(self, "preview_thumbnail_lbl") and self.preview_thumbnail_lbl.winfo_exists():
            self.preview_thumbnail_lbl.config(image="", text="Κάντε κλικ σε γραμμή", compound="center")
        self._preview_photo = None
        self._preview_pdf_path = ""
        self._preview_page = 0
        self._tab5_preview_row_index = -1
        if hasattr(self, "validation_report_text") and self.validation_report_text.winfo_exists():
            self.validation_report_text.config(state="normal")
            self.validation_report_text.delete("1.0", tk.END)
            self.validation_report_text.insert("1.0", "Εκτελέστε «Έλεγχος Βάσης» για νέα αναφορά.")
            self.validation_report_text.config(state="disabled")
        if hasattr(self, "dbprev") and self.dbprev.winfo_exists():
            self.dbprev.config(state="normal")
            self.dbprev.delete("1.0", tk.END)
            self.dbprev.config(state="disabled")
        self._s("Έγινε επαναφορά. Ξεκινήστε νέο βιβλίο.")

    def _build_tab2(self):
        f = self.tab2
        self._section_header(f, "🔍  Σήμανση PDF — Εντοπισμός & Εφαρμογή Markers")
        card = self._card(f)
        self._label(card, "Original PDF:")
        self.tab2_original_pdf_lbl = tk.Label(card, text="—", bg=WHITE, fg=TEXT_DARK, font=("Arial", 9), anchor="w", justify="left")
        self.tab2_original_pdf_lbl.pack(anchor="w", fill="x", pady=(0, 2))
        self._label(card, "Marked PDF (δημιουργείται μετά τη Σήμανση):")
        self.tab2_marked_pdf_lbl = tk.Label(card, text="—", bg=WHITE, fg=TEXT_DARK, font=("Arial", 9), anchor="w", justify="left")
        self.tab2_marked_pdf_lbl.pack(anchor="w", fill="x", pady=(0, 6))
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
        self._label(card, "Φάκελος MP3:")
        mp3_row = tk.Frame(card, bg=WHITE)
        mp3_row.pack(fill="x", pady=3)
        self.mp3_folder_entry = tk.Entry(
            mp3_row,
            textvariable=self.dv["mp3_folder"],
            font=("Arial", 9),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        )
        self.mp3_folder_entry.pack(side="left", fill="x", expand=True)
        _btn(mp3_row, "Επιλογή Φακέλου MP3", self._pick_mp3_folder, width=22).pack(side="right", padx=(6, 0))
        self.mp3_files_count_lbl = tk.Label(
            card, text="MP3 Files Found: 0", bg=WHITE, fg=TEXT_DARK, font=("Arial", 9)
        )
        self.mp3_files_count_lbl.pack(anchor="w", pady=(2, 0))
        self._label(card, "Έλεγχος MP3 — Αποτελέσματα:")
        mp3_report_frame = tk.Frame(card, bg=WHITE)
        mp3_report_frame.pack(fill="both", expand=True, pady=3)
        scrollbar_mp3 = ttk.Scrollbar(mp3_report_frame)
        self.mp3_validation_report = tk.Text(
            mp3_report_frame,
            font=("Consolas", 9),
            bg=GREY_LIGHT,
            fg=TEXT_DARK,
            height=10,
            wrap="word",
            state="disabled",
            yscrollcommand=scrollbar_mp3.set,
        )
        scrollbar_mp3.config(command=self.mp3_validation_report.yview)
        scrollbar_mp3.pack(side="right", fill="y")
        self.mp3_validation_report.pack(side="left", fill="both", expand=True)
        self.mp3_validation_report.insert("1.0", "Επιλέξτε φάκελο MP3 και πατήστε «Έλεγχος MP3» για αναφορά.")
        self.btn_validate_mp3 = _btn(
            card,
            "🔊  Έλεγχος MP3",
            self._validate_mp3,
            bg=GREEN,
            width=18,
        )
        self.btn_validate_mp3.pack(anchor="w", pady=4)
        self.btn_validate_mp3.config(state="disabled")
        tk.Frame(card, bg=GREY_MED, height=1).pack(fill="x", pady=12)
        self.btn_gen_db = _btn(
            card,
            "📊  Δημιουργία database.xlsx",
            self._gen_db,
            big=True,
        )
        self.btn_gen_db.pack(fill="x", pady=6)
        self.btn_gen_db.config(state="disabled")
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

    def _build_tab6(self):
        """Preflight validation tab: validate database and source structure, show report in UI."""
        f = self.tab6
        self._section_header(f, "🔍  6. Έλεγχος Βάσης")
        card = self._card(f)
        tk.Label(
            card,
            text="Επαληθεύει ότι η βάση και οι πηγές είναι σωστές. Επιλέξτε φάκελο MP3 στο Tab 4.",
            bg=WHITE,
            fg=TEXT_DARK,
            font=("Arial", 9),
        ).pack(anchor="w", pady=(0, 6))
        _btn(card, "Έλεγχος Βάσης / Validate Database", self._run_preflight_validation).pack(anchor="w", pady=4)
        report_frame = tk.Frame(card, bg=WHITE)
        report_frame.pack(fill="both", expand=True, pady=8)
        scrollbar = ttk.Scrollbar(report_frame)
        self.validation_report_text = tk.Text(
            report_frame,
            wrap="word",
            font=("Consolas", 10),
            bg=GREY_LIGHT,
            fg=TEXT_DARK,
            relief="flat",
            state="disabled",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.validation_report_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.validation_report_text.pack(side="left", fill="both", expand=True)
        self.validation_report_text.tag_configure("status_ok", foreground=GREEN, font=("Consolas", 10, "bold"))
        self.validation_report_text.tag_configure("status_warnings", foreground="#b8860b", font=("Consolas", 10, "bold"))
        self.validation_report_text.tag_configure("status_errors", foreground="#c03030", font=("Consolas", 10, "bold"))

    def _build_tab7(self):
        """Bunny.net Preparation — no upload; prepare and display data for future upload."""
        f = self.tab7
        self._section_header(f, "☁️  7. Bunny.net Preparation")
        card = self._card(f)
        tk.Label(
            card,
            text="Ρυθμίστε τα πεδία για μελλοντική μεταφόρτωση. Δεν γίνεται ακόμα upload.",
            bg=WHITE,
            fg=TEXT_DARK,
            font=("Arial", 9),
        ).pack(anchor="w", pady=(0, 8))
        self._label(card, "Base CDN URL (e.g. https://fanari.b-cdn.net):")
        tk.Entry(
            card,
            textvariable=self.bunny_prep["base_cdn_url"],
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        ).pack(fill="x", pady=2)
        self._label(card, "Book slug (e.g. anastasimatarion):")
        tk.Entry(
            card,
            textvariable=self.bunny_prep["book_slug"],
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        ).pack(fill="x", pady=2)
        self._label(card, "Chapter code (e.g. AN01):")
        tk.Entry(
            card,
            textvariable=self.bunny_prep["chapter_code"],
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        ).pack(fill="x", pady=2)
        self._label(card, "Root remote folder (default: books):")
        tk.Entry(
            card,
            textvariable=self.bunny_prep["root_remote_folder"],
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        ).pack(fill="x", pady=2)
        self._label(card, "Thinkific Course Name:")
        tk.Entry(
            card,
            textvariable=self.bunny_prep["thinkific_course_name"],
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        ).pack(fill="x", pady=2)
        self._label(card, "Thinkific Chapter Name:")
        tk.Entry(
            card,
            textvariable=self.bunny_prep["thinkific_chapter_name"],
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        ).pack(fill="x", pady=2)
        self._label(card, "FlipBuilder Book Name (optional):")
        tk.Entry(
            card,
            textvariable=self.bunny_prep["flipbuilder_book_name"],
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
        ).pack(fill="x", pady=2)
        self._label(card, "API Key (optional, not used yet):")
        tk.Entry(
            card,
            textvariable=self.bunny_prep["api_key"],
            font=("Arial", 10),
            bg=GREY_LIGHT,
            relief="flat",
            bd=5,
            show="*",
        ).pack(fill="x", pady=2)
        tk.Frame(card, bg=GREY_MED, height=1).pack(fill="x", pady=10)
        btn_row = tk.Frame(card, bg=WHITE)
        btn_row.pack(fill="x", pady=4)
        _btn(btn_row, "Preview Bunny URLs", self._preview_bunny_urls, bg=GREEN, width=20).pack(side="left", padx=(0, 8))
        _btn(btn_row, "Export Bunny Upload Manifest", self._export_bunny_manifest, width=26).pack(side="left")
        tk.Frame(card, bg=GREY_MED, height=1).pack(fill="x", pady=12)
        self._section_header(card, "Publishing Exports")
        pub_btn_row = tk.Frame(card, bg=WHITE)
        pub_btn_row.pack(fill="x", pady=4)
        _btn(pub_btn_row, "Preview Publishing Paths", self._preview_publishing_paths, bg=GREEN, width=22).pack(side="left", padx=(0, 8))
        _btn(pub_btn_row, "Export Bunny Manifest", self._export_publishing_bunny_manifest, width=20).pack(side="left", padx=(0, 8))
        _btn(pub_btn_row, "Export Thinkific Lesson List", self._export_thinkific_lessons, width=24).pack(side="left", padx=(0, 8))
        _btn(pub_btn_row, "Export FlipBuilder Audio Links", self._export_flipbuilder_links, width=26).pack(side="left")
        self._label(card, "Preview — row number, title, mp3 filename, bunny folder, bunny url, thinkific lesson title:")
        report_frame = tk.Frame(card, bg=WHITE)
        report_frame.pack(fill="both", expand=True, pady=4)
        scrollbar = ttk.Scrollbar(report_frame)
        self.bunny_preview_text = tk.Text(
            report_frame,
            wrap="word",
            font=("Consolas", 9),
            bg=GREY_LIGHT,
            fg=TEXT_DARK,
            relief="flat",
            state="disabled",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.bunny_preview_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.bunny_preview_text.pack(side="left", fill="both", expand=True)
        self.bunny_preview_text.insert("1.0", "Πατήστε «Preview Bunny URLs» ή «Preview Publishing Paths».")

    def _build_tab8(self):
        """Book Registry — load book_registry.xlsx, match chapter codes to parent books."""
        f = self.tab8
        self._section_header(f, "📚  Book Registry")
        card = self._card(f)
        tk.Label(
            card,
            text="Load book_registry.xlsx to understand which chapter codes belong to which book. No merge, no upload.",
            bg=WHITE,
            fg=TEXT_DARK,
            font=("Arial", 9),
        ).pack(anchor="w", pady=(0, 8))
        load_row = tk.Frame(card, bg=WHITE)
        load_row.pack(fill="x", pady=4)
        _btn(load_row, "Load Book Registry", self._load_book_registry, bg=GREEN, width=18).pack(side="left", padx=(0, 8))
        tk.Frame(card, bg=GREY_MED, height=1).pack(fill="x", pady=12)
        self._section_header(card, "Add New Book")
        add_fields = [
            "Book_Code",
            "Book_Title",
            "Book_Slug",
            "Thinkific_Course_Name",
            "Subscription_Group",
            "FlipBuilder_Book_Name",
            "Bookshelf_Name",
            "Bookshelf_Order",
            "Bunny_Root_Folder",
            "Chapter_List",
            "Notes",
        ]
        self.book_registry_add_vars = {k: tk.StringVar() for k in add_fields}
        add_grid = tk.Frame(card, bg=WHITE)
        add_grid.pack(fill="x", pady=4)
        for i, name in enumerate(add_fields):
            lbl = tk.Label(add_grid, text=name + ":", bg=WHITE, fg=TEXT_DARK, font=("Arial", 9), width=20, anchor="e")
            lbl.grid(row=i, column=0, sticky="e", padx=(0, 4), pady=2)
            ent = tk.Entry(add_grid, textvariable=self.book_registry_add_vars[name], font=("Arial", 10), bg=GREY_LIGHT, width=50)
            ent.grid(row=i, column=1, sticky="ew", padx=4, pady=2)
        add_grid.columnconfigure(1, weight=1)
        add_btn_row = tk.Frame(card, bg=WHITE)
        add_btn_row.pack(fill="x", pady=4)
        _btn(add_btn_row, "Add Book to Registry", self._add_book_to_registry, bg=GREEN, width=20).pack(side="left")
        tk.Frame(card, bg=GREY_MED, height=1).pack(fill="x", pady=12)
        self._label(card, "Loaded books (select one):")
        list_frame = tk.Frame(card, bg=WHITE)
        list_frame.pack(fill="both", expand=True, pady=4)
        scrollbar = ttk.Scrollbar(list_frame)
        self.book_registry_listbox = tk.Listbox(
            list_frame,
            font=("Consolas", 10),
            bg=GREY_LIGHT,
            fg=TEXT_DARK,
            selectmode="single",
            height=8,
            yscrollcommand=scrollbar.set,
        )
        self.book_registry_listbox.bind("<<ListboxSelect>>", self._on_book_registry_select)
        scrollbar.config(command=self.book_registry_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.book_registry_listbox.pack(side="left", fill="both", expand=True)
        self._label(card, "Selected book metadata:")
        self.book_registry_meta_text = tk.Text(
            card,
            wrap="word",
            font=("Consolas", 9),
            bg=GREY_LIGHT,
            fg=TEXT_DARK,
            height=6,
        )
        self.book_registry_meta_text.pack(fill="x", pady=2)
        self._label(card, "Chapter lookup — enter chapter code (e.g. AN01):")
        lookup_row = tk.Frame(card, bg=WHITE)
        lookup_row.pack(fill="x", pady=2)
        self.book_registry_chapter_var = tk.StringVar()
        tk.Entry(
            lookup_row,
            textvariable=self.book_registry_chapter_var,
            font=("Arial", 10),
            width=12,
            bg=GREY_LIGHT,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            lookup_row,
            text="Lookup",
            command=self._lookup_chapter_in_registry,
            bg=GREEN,
            fg=WHITE,
            font=("Arial", 9, "bold"),
            relief="flat",
            cursor="hand2",
        ).pack(side="left")
        self._label(card, "Preview — matching book for chapter:")
        self.book_registry_preview_text = tk.Text(
            card,
            wrap="word",
            font=("Consolas", 9),
            bg=GREY_LIGHT,
            fg=TEXT_DARK,
            height=8,
            state="disabled",
        )
        self.book_registry_preview_text.pack(fill="both", expand=True, pady=2)

    def _reload_book_registry_list(self, path: str):
        """Reload the books list from path and refresh listbox."""
        ok, books, errors = load_book_registry(path)
        if not ok:
            return
        self.book_registry_books = books
        self.book_registry_path = path
        self.book_registry_listbox.delete(0, tk.END)
        for b in books:
            code = b.get("Book_Code", "")
            title = (b.get("Book_Title", "") or "")[:50]
            slug = b.get("Book_Slug", "")
            self.book_registry_listbox.insert(tk.END, f"{code} | {slug} | {title}")

    def _add_book_to_registry(self):
        """Add new book from form to book_registry.xlsx."""
        path = self.book_registry_path if self.book_registry_path and os.path.isfile(self.book_registry_path) else None
        if not path:
            path = filedialog.asksaveasfilename(
                title="Select or create book_registry.xlsx",
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx"), ("All files", "*.*")],
            )
        if not path:
            return
        book = {
            "Book_Code": (self.book_registry_add_vars["Book_Code"].get() or "").strip(),
            "Book_Title": (self.book_registry_add_vars["Book_Title"].get() or "").strip(),
            "Book_Slug": (self.book_registry_add_vars["Book_Slug"].get() or "").strip(),
            "Thinkific_Course_Name": (self.book_registry_add_vars["Thinkific_Course_Name"].get() or "").strip(),
            "Subscription_Group": (self.book_registry_add_vars["Subscription_Group"].get() or "").strip(),
            "FlipBuilder_Book_Name": (self.book_registry_add_vars["FlipBuilder_Book_Name"].get() or "").strip(),
            "Bookshelf_Name": (self.book_registry_add_vars["Bookshelf_Name"].get() or "").strip(),
            "Bookshelf_Order": (self.book_registry_add_vars["Bookshelf_Order"].get() or "").strip(),
            "Bunny_Root_Folder": (self.book_registry_add_vars["Bunny_Root_Folder"].get() or "").strip(),
            "Chapter_List": (self.book_registry_add_vars["Chapter_List"].get() or "").strip(),
            "Is_Active": "",
            "Notes": (self.book_registry_add_vars["Notes"].get() or "").strip(),
        }
        ok, errors = append_book_to_registry(path, book)
        if not ok:
            messagebox.showerror("Add Book", "\n".join(errors))
            return
        self.book_registry_path = path
        self._reload_book_registry_list(path)
        messagebox.showinfo("Add Book", "Book added to registry successfully.")
        self._s("Book added to registry.")

    def _load_book_registry(self):
        """Load book_registry.xlsx via file dialog."""
        path = filedialog.askopenfilename(
            title="Load Book Registry",
            filetypes=[("Excel", "*.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return
        ok, books, errors = load_book_registry(path)
        if not ok:
            messagebox.showerror("Book Registry", "\n".join(errors))
            return
        self._reload_book_registry_list(path)
        self.book_registry_meta_text.delete("1.0", tk.END)
        self.book_registry_preview_text.config(state="normal")
        self.book_registry_preview_text.delete("1.0", tk.END)
        self.book_registry_preview_text.insert("1.0", f"Loaded {len(self.book_registry_books)} book(s) from {path}")
        self.book_registry_preview_text.config(state="disabled")
        self._s(f"Book registry loaded: {path}")

    def _on_book_registry_select(self, event):
        """Show selected book metadata."""
        sel = self.book_registry_listbox.curselection()
        if not sel or not self.book_registry_books:
            return
        idx = sel[0]
        if idx >= len(self.book_registry_books):
            return
        book = self.book_registry_books[idx]
        lines = []
        for k in ["Book_Code", "Book_Title", "Book_Slug", "Thinkific_Course_Name", "FlipBuilder_Book_Name", "Bunny_Root_Folder", "Chapter_List"]:
            v = book.get(k, "")
            lines.append(f"{k}: {v}")
        self.book_registry_meta_text.delete("1.0", tk.END)
        self.book_registry_meta_text.insert("1.0", "\n".join(lines))

    def _lookup_chapter_in_registry(self):
        """Look up chapter code in registry and show matching book."""
        ch = (self.book_registry_chapter_var.get() or "").strip()
        self.book_registry_preview_text.config(state="normal")
        self.book_registry_preview_text.delete("1.0", tk.END)
        if not ch:
            self.book_registry_preview_text.insert("1.0", "Enter a chapter code (e.g. AN01) and click Lookup.")
            self.book_registry_preview_text.config(state="disabled")
            return
        if not self.book_registry_books:
            self.book_registry_preview_text.insert("1.0", "Load Book Registry first.")
            self.book_registry_preview_text.config(state="disabled")
            return
        book = find_book_for_chapter(ch, self.book_registry_books)
        if not book:
            self.book_registry_preview_text.insert("1.0", f"No book found for chapter code: {ch}")
        else:
            lines = [
                f"Chapter code: {ch}",
                f"Book_Code: {book.get('Book_Code', '')}",
                f"Book_Title: {book.get('Book_Title', '')}",
                f"Book_Slug: {book.get('Book_Slug', '')}",
                f"Thinkific_Course_Name: {book.get('Thinkific_Course_Name', '')}",
                f"FlipBuilder_Book_Name: {book.get('FlipBuilder_Book_Name', '')}",
                f"Bunny_Root_Folder: {book.get('Bunny_Root_Folder', '')}",
            ]
            self.book_registry_preview_text.insert("1.0", "\n".join(lines))
        self.book_registry_preview_text.config(state="disabled")

    def _build_bunny_public_url(
        self, base_cdn_url: str, book_slug: str, chapter_code: str, filename: str
    ) -> str:
        """Build future public URL: BaseURL + / + BookSlug + / + ChapterCode + / + filename (URL-encoded)."""
        base = (base_cdn_url or "").strip().rstrip("/")
        slug = (book_slug or "").strip()
        code = (chapter_code or "").strip()
        if not base or not slug or not code or not filename:
            return ""
        return f"{base}/{quote(slug, safe='')}/{quote(code, safe='')}/{quote(filename, safe='')}"

    def _build_bunny_folder_path(
        self, root_remote_folder: str, book_slug: str, chapter_code: str
    ) -> str:
        """Build Bunny folder path: root/book_slug/chapter_code/ (e.g. books/anastasimatarion/AN01/)."""
        root = (root_remote_folder or "").strip().strip("/")
        slug = (book_slug or "").strip().strip("/")
        code = (chapter_code or "").strip().strip("/")
        if not root or not slug or not code:
            return ""
        return f"{root}/{slug}/{code}/"

    def _build_bunny_public_url_publishing(
        self,
        base_cdn_url: str,
        root_remote_folder: str,
        book_slug: str,
        chapter_code: str,
        mp3_filename: str,
    ) -> str:
        """Build Bunny public URL: BaseCDN + / + RootRemoteFolder + / + BookSlug + / + ChapterCode + / + mp3_filename."""
        base = (base_cdn_url or "").strip().rstrip("/")
        root = (root_remote_folder or "").strip().strip("/")
        slug = (book_slug or "").strip().strip("/")
        code = (chapter_code or "").strip().strip("/")
        if not base or not root or not slug or not code or not mp3_filename:
            return ""
        return f"{base}/{quote(root, safe='')}/{quote(slug, safe='')}/{quote(code, safe='')}/{quote(mp3_filename, safe='')}"

    def _validate_bunny_config(
        self,
        base_cdn_url: str,
        book_slug: str,
        chapter_code: str,
        source_mp3_files: List[str],
    ) -> Tuple[bool, List[str]]:
        """Validate Bunny configuration. Returns (ok, list of error messages). No network calls."""
        errors: List[str] = []
        base = (base_cdn_url or "").strip()
        if not base:
            errors.append("Base CDN URL is required.")
        elif not base.lower().startswith("https://"):
            errors.append("Base CDN URL must start with https://")
        slug = (book_slug or "").strip()
        if not slug:
            errors.append("Book slug is required.")
        elif " " in slug:
            errors.append("Book slug must not contain spaces.")
        if not (chapter_code or "").strip():
            errors.append("Chapter code is required.")
        if not source_mp3_files:
            errors.append("No source MP3 files. Select MP3 folder in Tab 4.")
        ordered = sorted(self.mrks, key=lambda m: (m.page, m.y)) if self.mrks else []
        if ordered and len(source_mp3_files) < len(ordered):
            errors.append(f"Fewer source MP3 files ({len(source_mp3_files)}) than hymn rows ({len(ordered)}).")
        seen = set()
        for f in source_mp3_files:
            if f in seen:
                errors.append(f"Duplicate filename: {f}")
            seen.add(f)
        pattern_res = validate_mp3_filename_pattern(source_mp3_files)
        for w in pattern_res.get("warnings", []):
            errors.append(w)
        return (len(errors) == 0, errors)

    def _get_bunny_manifest_rows(self) -> List[dict]:
        """Build list of dicts: row_number, title, source_mp3_filename, filename (canonical), future_public_url."""
        base = (self.bunny_prep["base_cdn_url"].get() or "").strip()
        book_slug = (self.bunny_prep["book_slug"].get() or "").strip()
        chapter_code = (self.bunny_prep["chapter_code"].get() or "").strip()
        mp3_folder = self.get_mp3_folder()
        source_files = list_mp3_files_in_folder(mp3_folder) if mp3_folder else []
        ordered = sorted(self.mrks, key=lambda m: (m.page, m.y)) if self.mrks else []
        rows = []
        for i in range(max(len(ordered), len(source_files))):
            row_num = i + 1
            title = ""
            if i < len(self.assignments):
                title = (self.assignments[i]["song_title"].get() or "").strip()
            source_mp3_filename = source_files[i] if i < len(source_files) else ""
            canonical_filename = get_mp3_file(chapter_code, row_num) if chapter_code else ""
            future_url = (
                self._build_bunny_public_url(base, book_slug, chapter_code, canonical_filename)
                if canonical_filename
                else ""
            )
            rows.append({
                "row_number": row_num,
                "title": title,
                "source_mp3_filename": source_mp3_filename,
                "filename": canonical_filename,
                "future_public_url": future_url,
            })
        return rows

    def _preview_bunny_urls(self):
        """Validate config, build URLs, display in Tab 7 preview. No upload."""
        base = (self.bunny_prep["base_cdn_url"].get() or "").strip()
        book_slug = (self.bunny_prep["book_slug"].get() or "").strip()
        chapter_code = (self.bunny_prep["chapter_code"].get() or "").strip()
        mp3_folder = self.get_mp3_folder()
        source_files = list_mp3_files_in_folder(mp3_folder) if mp3_folder else []
        ok, errs = self._validate_bunny_config(base, book_slug, chapter_code, source_files)
        if not ok:
            messagebox.showerror("Bunny Configuration", "\n".join(errs))
            return
        rows = self._get_bunny_manifest_rows()
        lines = ["Row\tTitle\tSource MP3 Filename\tFuture Public URL", ""]
        for r in rows:
            lines.append(f"{r['row_number']}\t{r['title']}\t{r['source_mp3_filename']}\t{r['future_public_url']}")
        self.bunny_preview_text.config(state="normal")
        self.bunny_preview_text.delete("1.0", tk.END)
        self.bunny_preview_text.insert("1.0", "\n".join(lines))
        self.bunny_preview_text.config(state="disabled")
        self._s("Preview Bunny URLs ready.")

    def _export_bunny_manifest(self):
        """Export manifest with row number, title, filename, future public URL. No upload."""
        base = (self.bunny_prep["base_cdn_url"].get() or "").strip()
        book_slug = (self.bunny_prep["book_slug"].get() or "").strip()
        chapter_code = (self.bunny_prep["chapter_code"].get() or "").strip()
        mp3_folder = self.get_mp3_folder()
        source_files = list_mp3_files_in_folder(mp3_folder) if mp3_folder else []
        ok, errs = self._validate_bunny_config(base, book_slug, chapter_code, source_files)
        if not ok:
            messagebox.showerror("Bunny Configuration", "\n".join(errs))
            return
        path = filedialog.asksaveasfilename(
            title="Export Bunny Upload Manifest",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Excel (XLSX)", "*.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return
        rows = self._get_bunny_manifest_rows()
        fieldnames = ["row_number", "title", "filename", "future_public_url"]
        export_rows = [{"row_number": r["row_number"], "title": r["title"], "filename": r["filename"], "future_public_url": r["future_public_url"]} for r in rows]
        try:
            if path.lower().endswith(".xlsx"):
                try:
                    import openpyxl
                except ImportError:
                    messagebox.showerror("Export Error", "openpyxl is required for XLSX. Install with: pip install openpyxl")
                    return
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Bunny Upload Manifest"
                for col, name in enumerate(fieldnames, 1):
                    ws.cell(row=1, column=col, value=name)
                for row_idx, r in enumerate(export_rows, 2):
                    for col, key in enumerate(fieldnames, 1):
                        ws.cell(row=row_idx, column=col, value=r.get(key, ""))
                wb.save(path)
            else:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=fieldnames)
                    w.writeheader()
                    w.writerows(export_rows)
        except OSError as e:
            messagebox.showerror("Export Error", str(e))
            return
        self._s(f"Manifest saved: {path}")
        messagebox.showinfo("Export", f"Bunny upload manifest saved:\n{path}")

    def _build_database_rows_for_validation(self) -> List[dict]:
        """Build rows from current state (source of truth) for validation and publishing."""
        code = (self.dv["code"].get() or "").strip() or "BOOK"
        bunny = (self.dv["bunny"].get() or "").strip() or ""
        pdf = self.pdf_path.get().strip()
        mp3_folder = self.get_mp3_folder()
        mp3_files = list_mp3_files_in_folder(mp3_folder) if mp3_folder else []
        ordered = sorted(self.mrks, key=lambda m: (m.page, m.y)) if self.mrks else []
        rows = []
        for i, m in enumerate(ordered):
            if i >= len(self.assignments):
                break
            song_title = (self.assignments[i]["song_title"].get() or "").strip()
            mp3_code = get_mp3_code(code, i + 1)
            mp3_file = mp3_files[i] if i < len(mp3_files) else ""
            url = get_mp3_url(bunny, code, i + 1) if bunny else ""
            preview = ""
            if pdf and os.path.isfile(pdf):
                preview = extract_preview_text(pdf, m)
            rows.append({
                "song_title": song_title,
                "mp3_code": mp3_code,
                "mp3_file": mp3_file,
                "url": url,
                "page": getattr(m, "page", None),
                "y": getattr(m, "y", None),
                "preview_text": preview or "",
            })
        return rows

    def _validate_publishing_export(self) -> Tuple[bool, List[str]]:
        """Validate before publishing export. Returns (ok, errors). Blocks if validation has errors."""
        errors: List[str] = []
        base = (self.bunny_prep["base_cdn_url"].get() or "").strip()
        if not base:
            errors.append("Base CDN URL is required.")
        elif not base.lower().startswith("https://"):
            errors.append("Base CDN URL must start with https://")
        book_slug = (self.bunny_prep["book_slug"].get() or "").strip()
        if not book_slug:
            errors.append("Book slug is required.")
        chapter_code = (self.bunny_prep["chapter_code"].get() or "").strip()
        if not chapter_code:
            errors.append("Chapter code is required.")
        rows = self._build_database_rows_for_validation()
        mp3_folder = self.get_mp3_folder()
        mp3_files = list_mp3_files_in_folder(mp3_folder) if mp3_folder else []
        result = run_full_validation(
            rows,
            mp3_folder=mp3_folder,
            mp3_files=mp3_files,
            mp3_count=len(mp3_files),
            pdf_path=self.pdf_path.get().strip(),
        )
        status_kind = result.get("status_kind", "errors")
        if status_kind == "errors":
            errors.append("Database validation has errors. Run Tab 6 Έλεγχος Βάσης and fix errors first.")
        for i, r in enumerate(rows):
            title = (r.get("song_title") or "").strip()
            mp3_file = (r.get("mp3_file") or "").strip()
            if not title:
                errors.append(f"Row {i + 1}: empty lesson title.")
            if not mp3_file:
                errors.append(f"Row {i + 1}: empty MP3 filename.")
        seen = set()
        for r in rows:
            f = (r.get("mp3_file") or "").strip()
            if f and f in seen:
                errors.append(f"Duplicate MP3 filename: {f}")
            if f:
                seen.add(f)
        return (len(errors) == 0, errors)

    def _get_publishing_rows(self) -> List[dict]:
        """Build publishing rows from validated database. One row per hymn."""
        base = (self.bunny_prep["base_cdn_url"].get() or "").strip()
        root = (self.bunny_prep["root_remote_folder"].get() or "").strip() or "books"
        book_slug = (self.bunny_prep["book_slug"].get() or "").strip()
        chapter_code = (self.bunny_prep["chapter_code"].get() or "").strip()
        thinkific_course = (self.bunny_prep["thinkific_course_name"].get() or "").strip()
        thinkific_chapter = (self.bunny_prep["thinkific_chapter_name"].get() or "").strip()
        rows = self._build_database_rows_for_validation()
        out = []
        for i, r in enumerate(rows):
            row_num = i + 1
            title = (r.get("song_title") or "").strip()
            mp3_filename = get_mp3_file(chapter_code, row_num) if chapter_code else ""
            bunny_folder = self._build_bunny_folder_path(root, book_slug, chapter_code)
            bunny_url = self._build_bunny_public_url_publishing(
                base, root, book_slug, chapter_code, mp3_filename
            )
            thinkific_lesson_title = f"{chapter_code} – {title}" if chapter_code and title else title
            out.append({
                "row_number": row_num,
                "chapter_code": chapter_code,
                "title": title,
                "mp3_filename": mp3_filename,
                "bunny_folder": bunny_folder,
                "bunny_public_url": bunny_url,
                "thinkific_lesson_title": thinkific_lesson_title,
                "thinkific_course_name": thinkific_course,
                "thinkific_chapter_name": thinkific_chapter,
                "audio_url": bunny_url,
            })
        return out

    def _preview_publishing_paths(self):
        """Preview publishing paths. Uses validated database. No network."""
        ok, errs = self._validate_publishing_export()
        if not ok:
            messagebox.showerror("Publishing Export", "\n".join(errs))
            return
        rows = self._get_publishing_rows()
        lines = [
            "Row\tTitle\tMP3 Filename\tBunny Folder\tBunny URL\tThinkific Lesson Title",
            "",
        ]
        for r in rows:
            lines.append(
                f"{r['row_number']}\t{r['title']}\t{r['mp3_filename']}\t{r['bunny_folder']}\t{r['bunny_public_url']}\t{r['thinkific_lesson_title']}"
            )
        self.bunny_preview_text.config(state="normal")
        self.bunny_preview_text.delete("1.0", tk.END)
        self.bunny_preview_text.insert("1.0", "\n".join(lines))
        self.bunny_preview_text.config(state="disabled")
        self._s("Preview Publishing Paths ready.")

    def _save_export_file(
        self,
        rows: List[dict],
        fieldnames: List[str],
        default_title: str,
        default_name: str,
    ) -> bool:
        """Save export to CSV or XLSX. Returns True if saved."""
        path = filedialog.asksaveasfilename(
            title=default_title,
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Excel (XLSX)", "*.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return False
        export_rows = [{k: r.get(k, "") for k in fieldnames} for r in rows]
        try:
            if path.lower().endswith(".xlsx"):
                try:
                    import openpyxl
                except ImportError:
                    messagebox.showerror("Export Error", "openpyxl required for XLSX. pip install openpyxl")
                    return False
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = default_name[:31]
                for col, name in enumerate(fieldnames, 1):
                    ws.cell(row=1, column=col, value=name)
                for row_idx, r in enumerate(export_rows, 2):
                    for col, key in enumerate(fieldnames, 1):
                        ws.cell(row=row_idx, column=col, value=r.get(key, ""))
                wb.save(path)
            else:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=fieldnames)
                    w.writeheader()
                    w.writerows(export_rows)
        except OSError as e:
            messagebox.showerror("Export Error", str(e))
            return False
        self._s(f"Exported: {path}")
        messagebox.showinfo("Export", f"Saved:\n{path}")
        return True

    def _export_publishing_bunny_manifest(self):
        """Export Bunny manifest: row_number, title, mp3_filename, bunny_folder, bunny_public_url."""
        ok, errs = self._validate_publishing_export()
        if not ok:
            messagebox.showerror("Publishing Export", "\n".join(errs))
            return
        rows = self._get_publishing_rows()
        fieldnames = ["row_number", "title", "mp3_filename", "bunny_folder", "bunny_public_url"]
        self._save_export_file(rows, fieldnames, "Export Bunny Manifest", "Bunny Manifest")

    def _export_thinkific_lessons(self):
        """Export Thinkific lesson list."""
        ok, errs = self._validate_publishing_export()
        if not ok:
            messagebox.showerror("Publishing Export", "\n".join(errs))
            return
        rows = self._get_publishing_rows()
        fieldnames = [
            "row_number",
            "chapter_code",
            "lesson_title",
            "thinkific_course_name",
            "thinkific_chapter_name",
            "audio_url",
            "mp3_filename",
        ]
        thinkific_rows = [
            {
                "row_number": r["row_number"],
                "chapter_code": r["chapter_code"],
                "lesson_title": r["thinkific_lesson_title"],
                "thinkific_course_name": r["thinkific_course_name"],
                "thinkific_chapter_name": r["thinkific_chapter_name"],
                "audio_url": r["audio_url"],
                "mp3_filename": r["mp3_filename"],
            }
            for r in rows
        ]
        self._save_export_file(
            thinkific_rows,
            fieldnames,
            "Export Thinkific Lesson List",
            "Thinkific Lessons",
        )

    def _export_flipbuilder_links(self):
        """Export FlipBuilder audio links."""
        ok, errs = self._validate_publishing_export()
        if not ok:
            messagebox.showerror("Publishing Export", "\n".join(errs))
            return
        rows = self._get_publishing_rows()
        fieldnames = ["row_number", "title", "audio_url", "mp3_filename"]
        flip_rows = [
            {
                "row_number": r["row_number"],
                "title": r["title"],
                "audio_url": r["audio_url"],
                "mp3_filename": r["mp3_filename"],
            }
            for r in rows
        ]
        self._save_export_file(
            flip_rows,
            fieldnames,
            "Export FlipBuilder Audio Links",
            "FlipBuilder Links",
        )

    def _run_preflight_validation(self):
        """Build rows from current state, run full validation, show report in UI."""
        self.reset_mp3_runtime_state()
        rows = self._build_database_rows_for_validation()
        mp3_folder = self.get_mp3_folder()
        mp3_files = list_mp3_files_in_folder(mp3_folder) if mp3_folder else []
        result = run_full_validation(
            rows,
            mp3_folder=mp3_folder,
            mp3_files=mp3_files,
            mp3_count=len(mp3_files),
            pdf_path=self.pdf_path.get().strip(),
        )
        self.validation_report_text.config(state="normal")
        self.validation_report_text.delete("1.0", tk.END)
        report = result.get("report_lines") or []
        status_text = result.get("status_text") or ""
        status_kind = result.get("status_kind") or "errors"
        content = "\n".join(report)
        self.validation_report_text.insert("1.0", content)
        # Color the STATUS line (find it and tag it)
        start = content.find("STATUS:")
        if start >= 0:
            end = content.find("\n", start)
            if end < 0:
                end = len(content)
            line_start = "1.0"
            line_end = "1.0"
            if start > 0:
                line_start = self.validation_report_text.index(f"1.0+{start}c")
            if end > start:
                line_end = self.validation_report_text.index(f"1.0+{end}c")
            tag = "status_ok" if status_kind == "ok" else "status_warnings" if status_kind == "warnings" else "status_errors"
            self.validation_report_text.tag_add(tag, line_start, line_end)
        self.validation_report_text.config(state="disabled")
        self._s("Έλεγχος βάσης ολοκληρώθηκε.")

    def _on_tab_changed(self, event):
        """Refresh content when tab selected: Tab 2 = PDF labels, Tab 4 = MP3 status, Tab 5 = song list."""
        try:
            nb = event.widget
            idx = nb.index(nb.select())
            if idx == 1:  # Tab 2
                if hasattr(self, "tab2_original_pdf_lbl") and self.tab2_original_pdf_lbl.winfo_exists():
                    self.tab2_original_pdf_lbl.config(text=self.pdf_path.get().strip() or "—")
                if hasattr(self, "tab2_marked_pdf_lbl") and self.tab2_marked_pdf_lbl.winfo_exists():
                    self.tab2_marked_pdf_lbl.config(text=self.marked_pdf_path.get().strip() or "—")
            elif idx == 3:  # Tab 4
                self._update_mp3_folder_status()
            elif idx == 4:  # Tab 5
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
        mp3_folder = self.get_mp3_folder()
        mp3_filenames_sorted = list_mp3_files_in_folder(mp3_folder) if mp3_folder else []
        ordered = sorted(self.mrks, key=lambda m: (m.page, m.y))
        for i, m in enumerate(ordered):
            mp3_file_name = get_mp3_file(code, i + 1)
            if i < len(mp3_filenames_sorted):
                final_title = song_title_from_mp3_file(mp3_filenames_sorted[i])
            else:
                final_title = ""
            self.assignments[i]["song_title"].set(final_title)
            row = tk.Frame(self.assign_inner, bg=GREY_LIGHT, relief="flat", bd=0, cursor="hand2")
            row.pack(fill="x", pady=1)
            row.bind("<Button-1>", lambda e, idx=i: self._on_preview_row(idx))
            tk.Label(row, text=f"#{i+1:03d}", width=5, bg=GREY_LIGHT, font=("Courier", 9)).pack(side="left", padx=2, pady=2)
            tk.Label(row, text=f"Σελ {m.page}", width=5, bg=GREY_LIGHT, font=("Courier", 9)).pack(side="left", padx=2, pady=2)
            tk.Label(row, text=f"Y{m.y:.0f}", width=5, bg=GREY_LIGHT, font=("Courier", 9)).pack(side="left", padx=2, pady=2)
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
            tk.Label(row, text=mp3_file_name, width=14, bg=GREY_LIGHT, fg=TEXT_DARK, font=("Courier", 9)).pack(side="left", padx=2, pady=2)
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

    def _pick_pdf(self):
        """Select Original PDF. Compute work_folder = dirname(original_pdf_path)."""
        path = filedialog.askopenfilename(
            title="Επιλογή Original PDF",
            filetypes=[("PDF αρχεία", "*.pdf"), ("Όλα τα αρχεία", "*.*")],
        )
        if not path:
            return
        self.original_pdf_path = path
        self.work_folder = os.path.dirname(path)
        self.pdf_path.set(path)
        if hasattr(self, "tab2_original_pdf_lbl") and self.tab2_original_pdf_lbl.winfo_exists():
            self.tab2_original_pdf_lbl.config(text=path)
        self._s(f"PDF: {os.path.basename(path)}")
        self._refresh_tab5()

    def _pick_mp3_folder(self):
        """Open folder selection; use selected path exactly. Never append input_mp3 or mp3."""
        selected_folder = filedialog.askdirectory(title="Επιλογή Φακέλου MP3")
        if selected_folder:
            self.source_mp3_folder = selected_folder
            self.dv["mp3_folder"].set(selected_folder)
            files = list_mp3_files_in_folder(selected_folder)
            self._update_mp3_folder_status()
            if len(files) == 0:
                messagebox.showwarning(
                    "No MP3 Files Found",
                    "The selected folder does not contain any .mp3 files.",
                )
            self._s(f"Φάκελος MP3: {selected_folder}")

    def _update_mp3_folder_status(self) -> None:
        """Update Tab 4: MP3 folder path, file count, validation report, and button state."""
        mp3_folder = self.get_mp3_folder()
        files = list_mp3_files_in_folder(mp3_folder) if mp3_folder else []
        count = len(files)
        # Update count label
        if hasattr(self, "mp3_files_count_lbl") and self.mp3_files_count_lbl.winfo_exists():
            self.mp3_files_count_lbl.config(text=f"MP3 Files Found: {count}")
        # Update validation report
        if hasattr(self, "mp3_validation_report") and self.mp3_validation_report.winfo_exists():
            self.mp3_validation_report.config(state="normal")
            self.mp3_validation_report.delete("1.0", tk.END)
            if not mp3_folder:
                self.mp3_validation_report.insert("1.0", "Επιλέξτε φάκελο MP3 και πατήστε «Έλεγχος MP3» για αναφορά.")
            else:
                lines = [
                    "MP3 VALIDATION REPORT",
                    "",
                    f"MP3 folder: {mp3_folder}",
                    "",
                ]
                if count == 0:
                    lines.extend([
                        "No MP3 files found in the selected folder.",
                        "Please select a folder that contains MP3 files.",
                    ])
                else:
                    lines.append(f"MP3 Files Found: {count}")
                self.mp3_validation_report.insert("1.0", "\n".join(lines))
            self.mp3_validation_report.config(state="disabled")
        # Enable/disable buttons based on MP3 count
        self._update_mp3_buttons_state(count > 0)

    def _update_mp3_buttons_state(self, enabled: bool) -> None:
        """Enable or disable Έλεγχος MP3 and Δημιουργία database.xlsx buttons."""
        state = "normal" if enabled else "disabled"
        if hasattr(self, "btn_validate_mp3") and self.btn_validate_mp3.winfo_exists():
            self.btn_validate_mp3.config(state=state)
        if hasattr(self, "btn_gen_db") and self.btn_gen_db.winfo_exists():
            self.btn_gen_db.config(state=state)

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
        folder = self.work_folder or os.path.dirname(pdf)
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
        self.marked_pdf_path.set(out_path)
        if hasattr(self, "tab2_marked_pdf_lbl") and self.tab2_marked_pdf_lbl.winfo_exists():
            self.tab2_marked_pdf_lbl.config(text=out_path)
        self._s(f"✅ Αποθηκεύτηκε: {out_path}  ({count} κουμπιά)")
        messagebox.showinfo(
            "Έτοιμο!",
            f"✅ Marked PDF:\n{out_path}\n\n{count} κουμπιά τοποθετήθηκαν.",
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
        """Validate MP3 filenames: numbering (missing, duplicate), pattern. Display in Tab 4 report."""
        mp3_folder = self.get_mp3_folder()
        if not mp3_folder or not mp3_folder.strip():
            messagebox.showwarning(
                "Φάκελος MP3",
                "Επιλέξτε φάκελο MP3 με το κουμπί «Επιλογή Φακέλου MP3».",
            )
            return
        if not os.path.isdir(mp3_folder):
            messagebox.showerror("Φάκελος MP3", f"Ο φάκελος δεν υπάρχει: {mp3_folder}")
            return
        files = list_mp3_files_in_folder(mp3_folder)
        num_res = validate_mp3_numbering(files)
        pattern_res = validate_mp3_filename_pattern(files)
        errs = (num_res.get("errors") or []) + (pattern_res.get("errors") or [])
        warns = (num_res.get("warnings") or []) + (pattern_res.get("warnings") or [])
        lines = [
            "MP3 VALIDATION REPORT",
            "",
            f"MP3 Folder: {mp3_folder}",
            f"MP3 Files Found: {len(files)}",
            "",
            f"Errors: {len(errs)}",
            f"Warnings: {len(warns)}",
            "",
        ]
        if errs:
            lines.append("--- ERRORS ---")
            lines.extend(errs)
            lines.append("")
        if warns:
            lines.append("--- WARNINGS ---")
            lines.extend(warns)
            lines.append("")
        if not errs and not warns and files:
            lines.append("OK — All MP3 filenames valid (NNN Title.mp3).")
            self._s("✅ Έλεγχος MP3 OK")
        elif not errs and warns:
            lines.append("OK with warnings — review above.")
            self._s("⚠️ Έλεγχος MP3 με προειδοποιήσεις")
        else:
            lines.append("Issues detected — fix errors above.")
            self._s("⚠️ Έλεγχος MP3: προβλήματα")
        self.mp3_validation_report.config(state="normal")
        self.mp3_validation_report.delete("1.0", tk.END)
        self.mp3_validation_report.insert("1.0", "\n".join(lines))
        self.mp3_validation_report.config(state="disabled")

    def _gen_db(self):
        if not self.mrks:
            messagebox.showerror(
                "Σφάλμα",
                "Εκτελέστε πρώτα «Εντοπισμός Markers» (Tab 2).",
            )
            return
        pdf = self.pdf_path.get().strip()
        fo = self.work_folder or (os.path.dirname(pdf) if pdf else "")
        if not fo:
            messagebox.showerror("Σφάλμα", "Επιλέξτε Original PDF (Tab 1).")
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

        source_mp3_files = list_mp3_files_in_folder(self.get_mp3_folder())
        path, count = build_database_xlsx(
            fo,
            self.mrks,
            code=code,
            bunny_base_url=bunny,
            assignments=assignments_data,
            source_mp3_files=source_mp3_files,
        )
        self._s(f"✅ {path}")
        n_source = len(source_mp3_files)
        messagebox.showinfo(
            "Έτοιμο!",
            f"✅ Βάση δεδομένων:\n{path}\n\nΕγγραφές: {count}\n"
            f"Αρχεία MP3 πηγής (χρησιμοποιήθηκαν): {n_source}",
        )
        lines = preview_lines(
            self.mrks,
            code=code,
            bunny_base_url=bunny,
            source_mp3_files=source_mp3_files,
        )
        self.dbprev.config(state="normal")
        self.dbprev.delete("1.0", "end")
        self.dbprev.insert("end", "\n".join(lines))
        self.dbprev.config(state="disabled")
        # Populate Tab 5 hymn mapping with same MP3 code/file/URL so user only fills hymn title
        self._refresh_tab5()
        self._s("Βάση δεδομένων και Αντιστοίχιση Ύμνων ενημερώθηκαν.")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
