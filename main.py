import os
import sys
import json
import uuid
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

import tkinter as tk
from tkinter import filedialog, messagebox

import fitz  # PyMuPDF
from PIL import Image, ImageTk


MARKER_CHAR = "\u25A0"  # ■
MARKER_COLOR = "#000000"  # legacy-style solid black square
SELECT_OUTLINE_COLOR = "#FFD700"  # visible highlight

# When two markers on the same page have y_pdf within this (PDF points), treat as same row for tie-break by x.
VERTICAL_CLOSE_EPS_PDF = 2.0

# Autosave safety
AUTOSAVE_INTERVAL_MS = 30000
TMP_SUFFIX = "_markers_tmp.json"


@dataclass
class Marker:
    id: str  # stable unique id within session
    marker_no: int  # global book order index (1..N) after compact / recalculate
    page_no: int  # 1-indexed page number
    x_pdf: float  # PDF points
    y_pdf: float  # PDF points


@dataclass
class UndoAddAction:
    marker_id: str
    page_no: int


class PDFMarkerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PDF Marker Tool")
        self.root.configure(bg="#2b1a1a")

        # PDF state
        self.doc: Optional[fitz.Document] = None
        self.filepath: Optional[str] = None
        self.current_page_index: int = 0  # 0-indexed for PyMuPDF

        # Marker state
        self.markers_by_page: Dict[int, List[Marker]] = {}
        # marker_no (global) -> Marker (same object as in markers_by_page)
        # Rebuilt whenever global numbering changes.
        self.marker_index_by_no: Dict[int, Marker] = {}
        # marker id -> Marker (same object as in markers_by_page)
        self.marker_index_by_id: Dict[str, Marker] = {}
        self.undo_stack: List[UndoAddAction] = []  # only "add marker" actions
        self.selected_marker_id: Optional[str] = None

        # Render state: zoom is a multiplier on top of "fit page in window" (1.0 = fitted).
        self.zoom: float = 1.0
        self.min_zoom: float = 0.5
        self.max_zoom: float = 3.0

        self.page_photos: List[ImageTk.PhotoImage] = []
        self.page_image_item_ids: List[int] = []
        # page_no -> (top_y_canvas, height_canvas, scale_x, scale_y, width_canvas)
        self.page_layout: Dict[int, Tuple[float, float, float, float, float]] = {}

        self.scale_x: float = 1.0  # legacy field, effective global scale for current render
        self.scale_y: float = 1.0  # legacy field, effective global scale for current render
        self.pix_width: int = 0
        self.pix_height: int = 0

        self.marker_overlay_tag = "marker_overlay"

        # Scrollbars (for wheel-hit testing; scrollbars sit beside the canvas)
        self._vbar: Optional[tk.Scrollbar] = None
        self._hbar: Optional[tk.Scrollbar] = None

        # Autosave / crash recovery state
        self.status_label: Optional[tk.Label] = None
        self._autosave_after_id: Optional[str] = None
        self._markers_lock = threading.Lock()
        self._save_thread: Optional[threading.Thread] = None
        self._save_state_lock = threading.Lock()
        self._save_pending: bool = False
        self._pending_status_text: str = "Auto-saved"

        self._canvas_resize_after_id: Optional[str] = None
        self._last_canvas_fit_size: Optional[Tuple[int, int]] = None

        self._build_ui()
        self._bind_events()

        self._update_labels_empty()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        self.root.minsize(920, 620)

        toolbar_outer = tk.Frame(self.root, bg="#4a1c1c", padx=4, pady=4)
        toolbar_outer.pack(fill=tk.X)

        row1 = tk.Frame(toolbar_outer, bg="#4a1c1c")
        row1.pack(fill=tk.X, pady=(0, 2))
        row2 = tk.Frame(toolbar_outer, bg="#4a1c1c")
        row2.pack(fill=tk.X)

        # ----- Row 1: Open | Save | Zoom | viewing info | marker count -----
        btn_open = tk.Button(
            row1,
            text="Open PDF",
            command=self.open_pdf,
            bg="#8b1a1a",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=8,
        )
        btn_open.pack(side=tk.LEFT, padx=(0, 4))

        btn_save_json = tk.Button(
            row1,
            text="Save JSON",
            command=self.save_markers_json,
            bg="#1a5c1a",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=8,
        )
        btn_save_json.pack(side=tk.LEFT, padx=4)

        btn_save_pdf = tk.Button(
            row1,
            text="Save PDF",
            command=self.save_pdf_with_markers,
            bg="#1a4a7a",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=8,
        )
        btn_save_pdf.pack(side=tk.LEFT, padx=4)

        self.page_label = tk.Label(
            row1, text="Viewing page - of -", bg="#4a1c1c", fg="white", font=("Arial", 11)
        )
        self.page_label.pack(side=tk.LEFT, padx=(8, 8))

        btn_zoom_out = tk.Button(
            row1,
            text="Zoom -",
            command=self.zoom_out,
            bg="#6a4a1a",
            fg="white",
            font=("Arial", 10),
            padx=8,
        )
        btn_zoom_out.pack(side=tk.LEFT, padx=4)

        btn_zoom_in = tk.Button(
            row1,
            text="Zoom +",
            command=self.zoom_in,
            bg="#6a4a1a",
            fg="white",
            font=("Arial", 10),
            padx=8,
        )
        btn_zoom_in.pack(side=tk.LEFT, padx=4)

        self.zoom_label = tk.Label(
            row1, text="Zoom: 100% (of fit)", bg="#4a1c1c", fg="white", font=("Arial", 10, "bold")
        )
        self.zoom_label.pack(side=tk.LEFT, padx=(4, 8))

        self.marker_count_label = tk.Label(
            row1,
            text="Markers on page: 0",
            bg="#4a1c1c",
            fg="#FFD700",
            font=("Arial", 10, "bold"),
        )
        self.marker_count_label.pack(side=tk.LEFT, padx=4)

        # ----- Row 2: Go to marker | marker nav | book tools | export | clear | undo -----
        go_frame = tk.Frame(row2, bg="#4a1c1c")
        go_frame.pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(
            go_frame,
            text="Go to marker:",
            bg="#4a1c1c",
            fg="white",
            font=("Arial", 10),
        ).pack(side=tk.LEFT, padx=(0, 4))
        self.go_to_marker_entry = tk.Entry(
            go_frame,
            width=6,
            font=("Arial", 10),
            justify=tk.CENTER,
        )
        self.go_to_marker_entry.pack(side=tk.LEFT, padx=2)
        btn_go_marker = tk.Button(
            go_frame,
            text="Go",
            command=self.go_to_marker,
            bg="#3a5a4a",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=8,
        )
        btn_go_marker.pack(side=tk.LEFT, padx=2)
        self.go_to_marker_entry.bind("<Return>", lambda e: self.go_to_marker())

        btn_prev_marker = tk.Button(
            row2,
            text="Previous Marker",
            command=self.prev_marker,
            bg="#2a6a4a",
            fg="white",
            font=("Arial", 9, "bold"),
            padx=6,
        )
        btn_prev_marker.pack(side=tk.LEFT, padx=4)

        btn_next_marker = tk.Button(
            row2,
            text="Next Marker",
            command=self.next_marker,
            bg="#2a6a4a",
            fg="white",
            font=("Arial", 9, "bold"),
            padx=6,
        )
        btn_next_marker.pack(side=tk.LEFT, padx=4)

        btn_recalc_book = tk.Button(
            row2,
            text="Recalculate Book Order",
            command=self.recalculate_book_order,
            bg="#2a4a6a",
            fg="white",
            font=("Arial", 9, "bold"),
            padx=6,
        )
        btn_recalc_book.pack(side=tk.LEFT, padx=4)

        btn_export_csv = tk.Button(
            row2,
            text="Export CSV",
            command=self.export_markers_csv,
            bg="#1a5c1a",
            fg="white",
            font=("Arial", 9, "bold"),
            padx=6,
        )
        btn_export_csv.pack(side=tk.LEFT, padx=4)

        btn_clear = tk.Button(
            row2,
            text="Clear Page",
            command=self.clear_current_page,
            bg="#7a1c1c",
            fg="white",
            font=("Arial", 9, "bold"),
            padx=6,
        )
        btn_clear.pack(side=tk.LEFT, padx=4)

        btn_undo = tk.Button(
            row2,
            text="Undo (Ctrl+Z)",
            command=self.undo_last_add,
            bg="#6a4a1a",
            fg="white",
            font=("Arial", 9),
            padx=6,
        )
        btn_undo.pack(side=tk.LEFT, padx=4)

        info = tk.Label(
            self.root,
            text="Continuous scroll mode: wheel/PageUp/PageDown/Home/End to scroll | Click to place ■ | Save PDF embeds markers | Save JSON for editing later | Right-click to delete",
            bg="#2b1a1a",
            fg="#FFD700",
            font=("Arial", 11),
        )
        info.pack(pady=4)

        # Reserve status strip, then let the canvas fill remaining height.
        self.status_label = tk.Label(
            self.root,
            text="Ready",
            bg="#2b1a1a",
            fg="#FFFFFF",
            font=("Arial", 9),
            anchor="w",
            padx=10,
            pady=2,
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        main = tk.Frame(self.root, bg="#2b1a1a")
        main.pack(fill=tk.BOTH, expand=True)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(main, bg="#1a1a1a", cursor="crosshair", highlightthickness=0, takefocus=True)
        self._vbar = tk.Scrollbar(main, orient=tk.VERTICAL, command=self.canvas.yview)
        self._hbar = tk.Scrollbar(main, orient=tk.HORIZONTAL, command=self.canvas.xview)

        self.canvas.configure(yscrollcommand=self._on_canvas_y_scroll, xscrollcommand=self._hbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self._vbar.grid(row=0, column=1, sticky="ns")
        self._hbar.grid(row=1, column=0, sticky="ew")

    def _bind_events(self) -> None:
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Button-2>", self.on_right_click)
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.root.bind_all("<MouseWheel>", self._on_mouse_wheel_global)
        self.root.bind_all("<Button-4>", self.on_mouse_wheel_linux)
        self.root.bind_all("<Button-5>", self.on_mouse_wheel_linux)

        # Keyboard shortcuts
        self.root.bind_all("<Delete>", self.on_delete_key)
        self.root.bind_all("<Escape>", self.on_escape)
        self.root.bind_all("<Control-z>", self.on_ctrl_z)

        # Continuous document navigation keys.
        self.root.bind_all("<Prior>", self.on_page_up_key)
        self.root.bind_all("<Next>", self.on_page_down_key)
        self.root.bind_all("<Home>", self.on_home_key)
        self.root.bind_all("<End>", self.on_end_key)

        self.canvas.bind("<Configure>", self._on_canvas_configure, add="+")

    def _show_unexpected(self, context: str, exc: BaseException) -> None:
        try:
            msg = str(exc)
        except Exception:
            msg = "<unavailable error message>"
        messagebox.showerror("Unexpected Error", f"{context}\n\n{msg}")

    def _on_canvas_configure(self, event: tk.Event) -> None:
        if self.doc is None or event.widget != self.canvas:
            return
        if self._canvas_resize_after_id is not None:
            try:
                self.root.after_cancel(self._canvas_resize_after_id)
            except Exception:
                pass
        self._canvas_resize_after_id = self.root.after(120, self._on_canvas_resize_debounced)

    def _on_canvas_resize_debounced(self) -> None:
        self._canvas_resize_after_id = None
        if self.doc is None:
            return
        self.root.update_idletasks()
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        if self._last_canvas_fit_size == (w, h):
            return
        # Re-render continuous stack for the new width while preserving viewport ratio.
        old_h = max(1, self.pix_height)
        old_y = float(self.canvas.canvasy(0))
        old_ratio = old_y / float(old_h)
        self.render_current_page()
        try:
            self.canvas.yview_moveto(max(0.0, min(1.0, old_ratio)))
        except Exception:
            pass

    def _canvas_viewport_size(self) -> Tuple[int, int]:
        self.root.update_idletasks()
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        return w, h

    def _on_canvas_y_scroll(self, first: str, last: str) -> None:
        self._vbar.set(first, last)
        if self.doc is not None:
            self.root.after_idle(self.update_labels_for_current_page)

    def _viewing_page_by_scroll(self) -> int:
        if self.doc is None:
            return 1
        if not self.page_layout:
            return max(1, min(self.doc.page_count, self.current_page_index + 1))
        _, y_top, _, vh = self._get_viewport_canvas_metrics()
        y_probe = y_top + (vh * 0.35)
        for page_no in sorted(self.page_layout.keys()):
            top, height, _, _, _ = self.page_layout[page_no]
            if top <= y_probe <= (top + height):
                return page_no
        # Fallback by nearest top.
        nearest = min(self.page_layout.items(), key=lambda kv: abs(kv[1][0] - y_probe))[0]
        return nearest

    def _page_at_canvas_point(self, canvas_x: float, canvas_y: float) -> Optional[int]:
        for page_no in sorted(self.page_layout.keys()):
            top, height, _, _, width = self.page_layout[page_no]
            if top <= canvas_y <= (top + height) and 0 <= canvas_x <= width:
                return page_no
        return None

    def _update_scrollbars_visibility(self) -> None:
        cw, _ = self._canvas_viewport_size()
        if self.pix_width > cw:
            self._hbar.grid(row=1, column=0, sticky="ew")
        else:
            self._hbar.grid_remove()
            try:
                self.canvas.xview_moveto(0.0)
            except Exception:
                pass
        # Continuous mode keeps vertical scrollbar available at all times.
        self._vbar.grid(row=0, column=1, sticky="ns")

    def on_close(self) -> None:
        try:
            self._stop_autosave()
            # Final protection: save before closing the app.
            try:
                if self._save_thread is not None and self._save_thread.is_alive():
                    self._save_thread.join(timeout=10)
            except Exception:
                pass
            if self.doc is not None:
                try:
                    self._save_markers_json_sync(status_text="Saved")
                except Exception:
                    self._set_status("Error saving")
                try:
                    self.doc.close()
                except Exception:
                    pass
        except Exception:
            pass
        if self._canvas_resize_after_id is not None:
            try:
                self.root.after_cancel(self._canvas_resize_after_id)
            except Exception:
                pass
        self._canvas_resize_after_id = None
        self.root.destroy()

    def _update_labels_empty(self) -> None:
        self.page_label.config(text="Viewing page - of -")
        self.marker_count_label.config(text="Markers on page: 0")
        self.zoom_label.config(text=f"Zoom: {int(round(self.zoom * 100))}% (of fit)")

    def get_current_page_no(self) -> int:
        return self._viewing_page_by_scroll()

    def get_markers_json_path(self) -> Optional[str]:
        if not self.filepath:
            return None
        folder = os.path.dirname(self.filepath)
        pdf_base = os.path.splitext(os.path.basename(self.filepath))[0]
        return os.path.join(folder, f"{pdf_base}_markers.json")

    def get_markers_tmp_json_path(self) -> Optional[str]:
        if not self.filepath:
            return None
        folder = os.path.dirname(self.filepath)
        pdf_base = os.path.splitext(os.path.basename(self.filepath))[0]
        return os.path.join(folder, f"{pdf_base}{TMP_SUFFIX}")

    def reset_session_state(self) -> None:
        self._stop_autosave()
        try:
            if self.doc is not None:
                self.doc.close()
        except Exception:
            pass

        self.doc = None
        self.filepath = None
        self.current_page_index = 0

        self.markers_by_page = {}
        self.marker_index_by_no = {}
        self.marker_index_by_id = {}
        self.undo_stack = []
        self.selected_marker_id = None

        try:
            self.canvas.delete("all")
        except Exception:
            pass
        self.page_photos = []
        self.page_image_item_ids = []
        self.page_layout = {}

        self.scale_x = 1.0
        self.scale_y = 1.0
        self.pix_width = 0
        self.pix_height = 0
        self.zoom = 1.0
        self._last_canvas_fit_size = None
        if self._canvas_resize_after_id is not None:
            try:
                self.root.after_cancel(self._canvas_resize_after_id)
            except Exception:
                pass
        self._canvas_resize_after_id = None

        self._update_labels_empty()

    def _set_status(self, text: str) -> None:
        try:
            if self.status_label is None:
                return
            if not self.status_label.winfo_exists():
                return
            self.status_label.config(text=text)
        except Exception:
            # Never let UI feedback crash the app.
            pass

    def _start_autosave(self) -> None:
        self._stop_autosave()
        if self.doc is None or not self.filepath:
            return
        self._autosave_after_id = self.root.after(AUTOSAVE_INTERVAL_MS, self._autosave_tick)

    def _stop_autosave(self) -> None:
        try:
            if self._autosave_after_id is not None:
                self.root.after_cancel(self._autosave_after_id)
        except Exception:
            pass
        self._autosave_after_id = None

    def _autosave_tick(self) -> None:
        self._autosave_after_id = None
        if self.doc is None or not self.filepath:
            return
        self._request_autosave(status_text="Auto-saved")
        # Schedule next tick.
        self._autosave_after_id = self.root.after(AUTOSAVE_INTERVAL_MS, self._autosave_tick)

    def _snapshot_markers_json_data(self) -> Dict[str, Any]:
        """
        Build markers JSON data from in-memory marker state.
        This is intentionally lightweight: it only copies marker coordinates and IDs.
        """
        if self.doc is None or not self.filepath:
            return {"file": "", "pages": {}}
        pdf_base_name = os.path.splitext(os.path.basename(self.filepath))[0]
        records: List[Tuple[int, int, int, float, float]] = []

        # Prevent concurrent mutation while we snapshot.
        # Copy only primitive values so the lock is held briefly.
        with self._markers_lock:
            for page_no, markers in self.markers_by_page.items():
                if page_no < 1:
                    continue
                for m in markers:
                    records.append((page_no, int(m.marker_no), int(m.page_no), float(m.x_pdf), float(m.y_pdf)))

        pages_out: Dict[str, List[Dict[str, Any]]] = {}
        for page_no, marker_no, page_no2, x, y in records:
            key = str(page_no)
            pages_out.setdefault(key, []).append(
                {"marker": marker_no, "page": page_no2, "x": x, "y": y}
            )

        return {"file": pdf_base_name, "pages": pages_out}

    def _safe_write_json_to_tmp_and_replace(self, json_path: str, tmp_path: str, data: Dict[str, Any]) -> None:
        # Write to temp, then replace atomically.
        # This prevents corrupted JSON overwriting the existing good file.
        tmp_dir = os.path.dirname(tmp_path)
        if tmp_dir and not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir, exist_ok=True)

        f = None
        try:
            f = open(tmp_path, "w", encoding="utf-8")
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                # fsync may not be supported everywhere; it's best-effort.
                pass
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass

        os.replace(tmp_path, json_path)

    def _save_markers_json_sync(self, status_text: str = "Saved") -> None:
        if self.doc is None or not self.filepath:
            return
        json_path = self.get_markers_json_path()
        tmp_path = self.get_markers_tmp_json_path()
        if not json_path or not tmp_path:
            return

        data = self._snapshot_markers_json_data()
        self._safe_write_json_to_tmp_and_replace(json_path=json_path, tmp_path=tmp_path, data=data)
        self._set_status(status_text)

    def _request_autosave(self, status_text: str = "Auto-saved") -> None:
        if self.doc is None or not self.filepath:
            return

        with self._save_state_lock:
            self._save_pending = True
            self._pending_status_text = status_text
            if self._save_thread is None or not self._save_thread.is_alive():
                self._save_thread = threading.Thread(target=self._save_worker_loop, daemon=True)
                self._save_thread.start()

    def _save_worker_loop(self) -> None:
        while True:
            with self._save_state_lock:
                if not self._save_pending:
                    return
                self._save_pending = False
                status_text = self._pending_status_text

            try:
                if self.doc is None or not self.filepath:
                    return
                json_path = self.get_markers_json_path()
                tmp_path = self.get_markers_tmp_json_path()
                if not json_path or not tmp_path:
                    return

                data = self._snapshot_markers_json_data()
                self._safe_write_json_to_tmp_and_replace(json_path=json_path, tmp_path=tmp_path, data=data)

                if self.root.winfo_exists():
                    self.root.after(0, lambda t=status_text: self._set_status(t))
            except Exception:
                if self.root.winfo_exists():
                    self.root.after(0, lambda: self._set_status("Error saving"))
                return

    def _total_marker_count(self) -> int:
        return sum(len(v) for v in self.markers_by_page.values())

    def _collect_all_markers_flat(self) -> List[Marker]:
        out: List[Marker] = []
        for page_no in sorted(self.markers_by_page.keys()):
            out.extend(self.markers_by_page[page_no])
        return out

    def _book_order_sort_key(self, m: Marker) -> Tuple[int, float, float]:
        # a) page ascending
        # b) y_pdf ascending (top to bottom in PyMuPDF page coords)
        # c) if very close vertically on same page, x_pdf breaks ties (via rounded y band)
        y_band = round(m.y_pdf / VERTICAL_CLOSE_EPS_PDF) * VERTICAL_CLOSE_EPS_PDF
        return (m.page_no, y_band, m.x_pdf)

    def _apply_global_book_order(self, sorted_markers: List[Marker]) -> None:
        """Assign marker_no 1..N globally and rebuild markers_by_page lists in sort order per page."""
        new_by_page: Dict[int, List[Marker]] = {}
        for i, m in enumerate(sorted_markers, start=1):
            m.marker_no = i
            new_by_page.setdefault(m.page_no, []).append(m)
        self.markers_by_page = new_by_page
        self._rebuild_marker_index()

    def _compact_global_marker_numbers(self) -> None:
        """Same ordering as Recalculate Book Order; reassigns 1..N without moving coordinates."""
        flat = self._collect_all_markers_flat()
        if not flat:
            return
        flat.sort(key=self._book_order_sort_key)
        self._apply_global_book_order(flat)

    def _rebuild_marker_index(self) -> None:
        self.marker_index_by_no = {}
        self.marker_index_by_id = {}
        for _, markers in self.markers_by_page.items():
            for m in markers:
                # marker_no should be unique after compaction/recalculation
                self.marker_index_by_no[m.marker_no] = m
                self.marker_index_by_id[m.id] = m

    def _next_global_marker_no(self) -> int:
        mx = 0
        for markers in self.markers_by_page.values():
            for m in markers:
                if m.marker_no > mx:
                    mx = m.marker_no
        return mx + 1

    @staticmethod
    def _marker_label_display(marker_no: int) -> str:
        return f"{marker_no:03d}"

    def open_pdf(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not path:
            return
        self.open_pdf_path(path)

    def open_pdf_path(self, path: str) -> None:
        """Open a PDF from disk (file dialog, Finder “Open With”, or command-line path)."""
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(path):
            messagebox.showerror("Error", f"PDF not found:\n{path}")
            return

        self.reset_session_state()
        self.filepath = path

        try:
            self.doc = fitz.open(path)
        except Exception as e:
            self.doc = None
            self.filepath = None
            messagebox.showerror("PDF Error", f"Failed to open PDF:\n{e}")
            return

        try:
            tmp_path = self.get_markers_tmp_json_path()
            source_path: Optional[str] = None
            recovered = False
            if tmp_path and os.path.exists(tmp_path):
                if messagebox.askyesno("Recover unsaved markers?", "Recover unsaved markers?"):
                    source_path = tmp_path
                    recovered = True
                else:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

            self.current_page_index = 0
            ok = self.load_markers_json_for_current_pdf(source_path=source_path)
            if recovered:
                if ok:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    self._set_status("Recovered")
                else:
                    # If recovery fails, fall back to normal markers JSON (if any).
                    self.load_markers_json_for_current_pdf()

            self.render_current_page()
            self._start_autosave()
        except Exception as e:
            messagebox.showerror("Unexpected Error", f"Failed to initialize viewer:\n{e}")

    def load_markers_json_for_current_pdf(self, source_path: Optional[str] = None) -> bool:
        with self._markers_lock:
            self.markers_by_page = {}
            self.undo_stack = []
            self.selected_marker_id = None
        json_path = source_path if source_path else self.get_markers_json_path()
        if not json_path:
            return True
        if not os.path.exists(json_path):
            # If caller requested a specific source (temp recovery), signal failure.
            return source_path is None

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("JSON Error", f"Invalid markers JSON:\n{e}")
            return False

        if not isinstance(data, dict):
            messagebox.showerror("JSON Error", "Invalid markers JSON: root must be an object.")
            return False

        pages_obj = data.get("pages", {})
        if not isinstance(pages_obj, dict):
            messagebox.showerror("JSON Error", "Invalid markers JSON: 'pages' must be an object.")
            return False

        if self.doc is None:
            return False

        page_count = self.doc.page_count
        new_by_page: Dict[int, List[Marker]] = {}

        for page_key, marker_list in pages_obj.items():
            try:
                page_no = int(page_key)
            except Exception:
                continue
            if page_no < 1 or page_no > page_count:
                continue
            if not isinstance(marker_list, list):
                continue

            loaded: List[Marker] = []
            for entry in marker_list:
                if not isinstance(entry, dict):
                    continue
                try:
                    x = float(entry.get("x"))
                    y = float(entry.get("y"))
                except Exception:
                    continue

                try:
                    marker_no = int(entry.get("marker", len(loaded) + 1))
                except Exception:
                    marker_no = len(loaded) + 1

                entry_page = entry.get("page", page_no)
                try:
                    entry_page_no = int(entry_page)
                except Exception:
                    entry_page_no = page_no

                if entry_page_no != page_no:
                    entry_page_no = page_no

                m = Marker(
                    id=uuid.uuid4().hex,
                    marker_no=marker_no,
                    page_no=page_no,
                    x_pdf=x,
                    y_pdf=y,
                )
                loaded.append(m)

            loaded.sort(key=lambda mm: mm.marker_no if mm.marker_no > 0 else 10**9)
            new_by_page[page_no] = loaded

        with self._markers_lock:
            self.markers_by_page = new_by_page
            self._compact_global_marker_numbers()
        return True

    def render_current_page(self, center_marker: Optional[Marker] = None) -> None:
        """Render PDF pages as one continuous vertical stack."""
        if self.doc is None:
            return
        try:
            self.render_page_image()
        except Exception as e:
            messagebox.showerror("Render Error", f"Failed to render page image:\n{e}")
            return

        self._update_scrollbars_visibility()
        if center_marker is not None:
            self._scroll_canvas_to_marker(center_marker)
        self.redraw_markers_overlay()
        self.update_labels_for_current_page()

        cw, ch = self._canvas_viewport_size()
        self._last_canvas_fit_size = (cw, ch)

    def render_page_image(self) -> None:
        assert self.doc is not None
        cw, _ = self._canvas_viewport_size()
        max_page_width_pdf = max(float(self.doc[i].rect.width) for i in range(self.doc.page_count))
        if max_page_width_pdf <= 0:
            raise ValueError("Invalid PDF page widths.")
        z_fit_width = float(cw) / max_page_width_pdf
        z_mat = max(0.05, z_fit_width * float(self.zoom))
        mat = fitz.Matrix(z_mat, z_mat)

        try:
            self.canvas.delete("pdf_image")
        except Exception:
            pass
        self.page_photos = []
        self.page_image_item_ids = []
        self.page_layout = {}

        y_cursor = 0.0
        max_w = 1
        page_gap = 8.0
        for idx in range(self.doc.page_count):
            page = self.doc[idx]
            rect = page.rect
            if rect.width <= 0 or rect.height <= 0:
                continue
            pix = page.get_pixmap(matrix=mat, alpha=False)
            if pix.width <= 0 or pix.height <= 0:
                continue
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            photo = ImageTk.PhotoImage(img)
            page_no = idx + 1
            item_id = self.canvas.create_image(0, y_cursor, anchor=tk.NW, image=photo, tags=("pdf_image",))
            self.page_photos.append(photo)
            self.page_image_item_ids.append(item_id)

            sx = float(pix.width) / float(rect.width)
            sy = float(pix.height) / float(rect.height)
            self.page_layout[page_no] = (y_cursor, float(pix.height), sx, sy, float(pix.width))
            max_w = max(max_w, pix.width)
            y_cursor += float(pix.height) + page_gap

        self.pix_width = max_w
        self.pix_height = max(1, int(y_cursor - page_gap if y_cursor > 0 else 1))
        self.scale_x = z_mat
        self.scale_y = z_mat
        self.canvas.configure(scrollregion=(0, 0, self.pix_width, self.pix_height))

    def update_labels_for_current_page(self) -> None:
        if self.doc is None:
            return
        total_pages = self.doc.page_count
        page_no = self.get_current_page_no()
        self.current_page_index = max(0, min(total_pages - 1, page_no - 1))
        page_title = f"Viewing page {page_no} of {total_pages}"
        self.page_label.config(text=page_title)

        count = len(self.markers_by_page.get(page_no, []))
        self.marker_count_label.config(text=f"Markers on page: {count}")

        self.zoom_label.config(text=f"Zoom: {int(round(self.zoom * 100))}% (of fit)")

    def get_marker_visual_metrics(self) -> Tuple[int, int, float, float, float]:
        # Legacy visual style:
        # - square size is stable (does not scale with zoom)
        # - label placement is stable relative to square
        symbol_font_size = 18
        label_font_size = 11

        label_offset_px = symbol_font_size * 0.85

        hit_radius_symbol_px = 12.0
        hit_radius_label_px = 14.0

        return symbol_font_size, label_font_size, label_offset_px, hit_radius_symbol_px, hit_radius_label_px

    def redraw_markers_overlay(self) -> None:
        try:
            self.canvas.delete(self.marker_overlay_tag)
        except Exception:
            pass

        if self.doc is None:
            return

        symbol_font_size, label_font_size, label_offset_px, _, _ = self.get_marker_visual_metrics()

        # Legacy workflow used a plain Arial glyph for the solid square.
        symbol_font = ("Arial", symbol_font_size, "bold")
        label_font = ("Arial", label_font_size, "bold")

        for page_no in sorted(self.markers_by_page.keys()):
            markers = self.markers_by_page.get(page_no, [])
            if not markers:
                continue
            layout = self.page_layout.get(page_no)
            if layout is None:
                continue
            page_top, _, sx, sy, _ = layout

            for m in markers:
                is_selected = m.id == self.selected_marker_id

                cx = m.x_pdf * sx
                cy = page_top + (m.y_pdf * sy)

                # Base marker: solid filled square (always black), no outline/oval.
                self.canvas.create_text(
                    cx,
                    cy,
                    text=MARKER_CHAR,
                    fill=MARKER_COLOR,
                    font=symbol_font,
                    anchor="center",
                    tags=(self.marker_overlay_tag, f"marker_{m.id}"),
                )

                # Selection highlight: only the number color changes.
                self.canvas.create_text(
                    cx,
                    cy + label_offset_px,
                    text=self._marker_label_display(m.marker_no),
                    fill=SELECT_OUTLINE_COLOR if is_selected else "#FFFFFF",
                    font=label_font,
                    anchor="center",
                    tags=(self.marker_overlay_tag, f"marker_{m.id}"),
                )

    def canvas_point_to_pdf(self, canvas_x: float, canvas_y: float, page_no: int) -> Tuple[float, float]:
        layout = self.page_layout.get(page_no)
        if layout is None:
            return 0.0, 0.0
        page_top, _, sx, sy, _ = layout
        return canvas_x / sx, (canvas_y - page_top) / sy

    def pdf_point_to_canvas(self, x_pdf: float, y_pdf: float, page_no: int) -> Tuple[float, float]:
        layout = self.page_layout.get(page_no)
        if layout is None:
            return 0.0, 0.0
        page_top, _, sx, sy, _ = layout
        return x_pdf * sx, page_top + (y_pdf * sy)

    def hit_test_marker(self, canvas_x: float, canvas_y: float) -> Optional[Marker]:
        if self.doc is None:
            return None
        page_no = self._page_at_canvas_point(canvas_x, canvas_y)
        if page_no is None:
            return None
        markers = self.markers_by_page.get(page_no, [])
        if not markers:
            return None

        symbol_font_size, label_font_size, label_offset_px, hit_radius_symbol_px, hit_radius_label_px = (
            self.get_marker_visual_metrics()
        )
        del symbol_font_size, label_font_size

        best: Optional[Marker] = None
        best_dist2 = float("inf")

        for m in markers:
            cx, cy = self.pdf_point_to_canvas(m.x_pdf, m.y_pdf, page_no)

            sym_dx = canvas_x - cx
            sym_dy = canvas_y - cy
            sym_dist2 = sym_dx * sym_dx + sym_dy * sym_dy

            lbl_cy = cy + label_offset_px
            lbl_dx = canvas_x - cx
            lbl_dy = canvas_y - lbl_cy
            lbl_dist2 = lbl_dx * lbl_dx + lbl_dy * lbl_dy

            if sym_dist2 <= hit_radius_symbol_px**2 or lbl_dist2 <= hit_radius_label_px**2:
                d2 = min(sym_dist2, lbl_dist2)
                if d2 < best_dist2:
                    best_dist2 = d2
                    best = m

        return best

    def on_left_click(self, event: tk.Event) -> None:
        try:
            if self.doc is None:
                return

            canvas_x = float(self.canvas.canvasx(event.x))
            canvas_y = float(self.canvas.canvasy(event.y))

            if canvas_x < 0 or canvas_y < 0 or canvas_x > self.pix_width or canvas_y > self.pix_height:
                return
            page_no = self._page_at_canvas_point(canvas_x, canvas_y)
            if page_no is None:
                return

            hit = self.hit_test_marker(canvas_x, canvas_y)
            if hit is not None:
                if hit.id != self.selected_marker_id:
                    self.selected_marker_id = hit.id
                    self.redraw_markers_overlay()
                    self.update_labels_for_current_page()
                return

            x_pdf, y_pdf = self.canvas_point_to_pdf(canvas_x, canvas_y, page_no)
            with self._markers_lock:
                markers = self.markers_by_page.get(page_no, [])

                new_id = uuid.uuid4().hex
                marker_no = self._next_global_marker_no()
                new_marker = Marker(
                    id=new_id, marker_no=marker_no, page_no=page_no, x_pdf=x_pdf, y_pdf=y_pdf
                )
                markers.append(new_marker)
                self.markers_by_page[page_no] = markers
                self.marker_index_by_no[new_marker.marker_no] = new_marker
                self.marker_index_by_id[new_marker.id] = new_marker

                self.undo_stack.append(UndoAddAction(marker_id=new_id, page_no=page_no))
                self.selected_marker_id = new_id

            self.redraw_markers_overlay()
            self.update_labels_for_current_page()
            self._request_autosave(status_text="Auto-saved")
        except Exception as e:
            self._show_unexpected("Failed to handle left click", e)

    def on_right_click(self, event: tk.Event) -> None:
        try:
            if self.doc is None:
                return

            canvas_x = float(self.canvas.canvasx(event.x))
            canvas_y = float(self.canvas.canvasy(event.y))

            if canvas_x < 0 or canvas_y < 0 or canvas_x > self.pix_width or canvas_y > self.pix_height:
                return

            hit = self.hit_test_marker(canvas_x, canvas_y)
            if hit is None:
                return

            self.delete_marker_by_id(hit.id, hit.page_no)
        except Exception as e:
            self._show_unexpected("Failed to handle right click", e)

    def delete_marker_by_id(self, marker_id: str, page_no: int) -> None:
        with self._markers_lock:
            markers = self.markers_by_page.get(page_no, [])
            if not markers:
                return

            idx = next((i for i, m in enumerate(markers) if m.id == marker_id), None)
            if idx is None:
                return

            removed = markers.pop(idx)
            self.markers_by_page[page_no] = markers

            if self.selected_marker_id == removed.id:
                self.selected_marker_id = None

            self._compact_global_marker_numbers()

        # Global numbers may change on every page; always refresh current view.
        self.redraw_markers_overlay()
        self.update_labels_for_current_page()
        self._request_autosave(status_text="Auto-saved")

    def on_delete_key(self, event: tk.Event) -> None:
        try:
            if self.doc is None:
                return
            if self.selected_marker_id is None:
                return

            marker_id = self.selected_marker_id
            found: Optional[Tuple[int, int]] = None
            for page_no, markers in self.markers_by_page.items():
                for i, m in enumerate(markers):
                    if m.id == marker_id:
                        found = (page_no, i)
                        break
                if found is not None:
                    break

            if found is None:
                self.selected_marker_id = None
                self.redraw_markers_overlay()
                self.update_labels_for_current_page()
                return

            page_no, _ = found
            self.delete_marker_by_id(marker_id, page_no)
        except Exception as e:
            self._show_unexpected("Failed to handle Delete key", e)

    def on_escape(self, event: tk.Event) -> None:
        try:
            if self.doc is None:
                return
            if self.selected_marker_id is None:
                return
            self.selected_marker_id = None
            self.redraw_markers_overlay()
        except Exception as e:
            self._show_unexpected("Failed to handle Escape", e)

    def on_ctrl_z(self, event: tk.Event) -> None:
        try:
            if self.doc is None:
                return
            self.undo_last_add()
        except Exception as e:
            self._show_unexpected("Failed to handle Ctrl+Z", e)

    def undo_last_add(self) -> None:
        if self.doc is None:
            return
        while self.undo_stack:
            action = self.undo_stack.pop()
            with self._markers_lock:
                markers = self.markers_by_page.get(action.page_no, [])
                marker = next((m for m in markers if m.id == action.marker_id), None)
                if marker is None:
                    continue

                markers.remove(marker)
                self.markers_by_page[action.page_no] = markers

                if self.selected_marker_id == marker.id:
                    self.selected_marker_id = None

                self._compact_global_marker_numbers()

            self.redraw_markers_overlay()
            self.update_labels_for_current_page()
            self._request_autosave(status_text="Auto-saved")
            return

    def clear_current_page(self) -> None:
        try:
            if self.doc is None:
                return
            page_no = self.get_current_page_no()

            if not self.markers_by_page.get(page_no):
                return

            ok = messagebox.askyesno("Confirm", f"Clear all markers on page {page_no}?")
            if not ok:
                return

            with self._markers_lock:
                self.markers_by_page[page_no] = []
                self.selected_marker_id = None
                self._compact_global_marker_numbers()

            self.redraw_markers_overlay()
            self.update_labels_for_current_page()
            self._request_autosave(status_text="Auto-saved")
        except Exception as e:
            self._show_unexpected("Failed to clear current page", e)

    def recalculate_book_order(self) -> None:
        try:
            if self.doc is None:
                return

            if self._total_marker_count() == 0:
                return

            ok = messagebox.askyesno(
                "Confirm",
                "Recalculate numbering for entire book?",
            )
            if not ok:
                return

            flat = self._collect_all_markers_flat()
            flat.sort(key=self._book_order_sort_key)
            with self._markers_lock:
                self._apply_global_book_order(flat)

            self.redraw_markers_overlay()
            self.update_labels_for_current_page()
            self._request_autosave(status_text="Auto-saved")

            messagebox.showinfo("Recalculate Book Order", "Book markers successfully renumbered")
        except Exception as e:
            self._show_unexpected("Failed to recalculate book order", e)

    def _find_marker_by_number(self, marker_num: int) -> Optional[Marker]:
        if self.marker_index_by_no:
            return self.marker_index_by_no.get(marker_num)
        # Fallback (should not happen often)
        for _, markers in self.markers_by_page.items():
            for m in markers:
                if m.marker_no == marker_num:
                    return m
        return None

    def _scroll_canvas_to_marker(self, m: Marker) -> None:
        """When zoomed past the window size, pan the view so the marker is visible (no document-style reading scroll)."""
        self.canvas.update_idletasks()
        cx, cy = self.pdf_point_to_canvas(m.x_pdf, m.y_pdf, m.page_no)
        _, _, label_offset_px, _, _ = self.get_marker_visual_metrics()
        cy_center = cy + label_offset_px * 0.45

        tw = max(1, self.pix_width)
        th = max(1, self.pix_height)
        vw = max(1, self.canvas.winfo_width())
        vh = max(1, self.canvas.winfo_height())

        max_left = max(0.0, float(tw - vw))
        max_top = max(0.0, float(th - vh))
        target_left = max(0.0, min(max_left, cx - vw / 2.0))
        target_top = max(0.0, min(max_top, cy_center - vh / 2.0))

        self.canvas.xview_moveto(target_left / float(tw))
        self.canvas.yview_moveto(target_top / float(th))

    def _select_marker_and_scroll(self, m: Marker) -> None:
        self.selected_marker_id = m.id
        self.render_current_page(center_marker=m)

    def prev_marker(self) -> None:
        try:
            if self.doc is None:
                return
            if not self.marker_index_by_no:
                return

            selected_marker = None
            if self.selected_marker_id is not None:
                selected_marker = self.marker_index_by_id.get(self.selected_marker_id)

            if selected_marker is None:
                target_no = max(self.marker_index_by_no.keys())
            else:
                target_no = selected_marker.marker_no - 1

            if target_no < 1:
                return
            found = self.marker_index_by_no.get(target_no)
            if found is None:
                return
            self._select_marker_and_scroll(found)
        except Exception as e:
            self._show_unexpected("Failed to navigate to previous marker", e)

    def next_marker(self) -> None:
        try:
            if self.doc is None:
                return
            if not self.marker_index_by_no:
                return

            selected_marker = None
            if self.selected_marker_id is not None:
                selected_marker = self.marker_index_by_id.get(self.selected_marker_id)

            if selected_marker is None:
                target_no = min(self.marker_index_by_no.keys())  # should be 1 after compaction
            else:
                target_no = selected_marker.marker_no + 1

            found = self.marker_index_by_no.get(target_no)
            if found is None:
                return
            self._select_marker_and_scroll(found)
        except Exception as e:
            self._show_unexpected("Failed to navigate to next marker", e)

    def go_to_marker(self) -> None:
        try:
            if self.doc is None:
                return

            raw = self.go_to_marker_entry.get().strip()
            if not raw:
                return

            try:
                num = int(raw, 10)
            except ValueError:
                messagebox.showwarning("Go to marker", "Enter a valid marker number.")
                return

            if num < 1:
                messagebox.showwarning("Go to marker", "Enter a valid marker number.")
                return

            found = self._find_marker_by_number(num)
            if found is None:
                messagebox.showinfo("Go to marker", "Marker not found")
                return

            self.selected_marker_id = found.id
            self.render_current_page(center_marker=found)
        except Exception as e:
            self._show_unexpected("Failed to go to marker", e)

    def export_markers_csv(self) -> None:
        if self.doc is None or not self.filepath:
            return

        try:
            json_path = self.filepath
            folder = os.path.dirname(json_path)
            pdf_base = os.path.splitext(os.path.basename(json_path))[0]
            csv_path = os.path.join(folder, f"{pdf_base}_markers.csv")

            # Always write header row even if there are no markers.
            markers_sorted = sorted(
                self.marker_index_by_no.values(), key=lambda m: m.marker_no
            )

            with open(csv_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("marker,page,x_pdf,y_pdf\n")
                for m in markers_sorted:
                    f.write(
                        f"{int(m.marker_no)},{int(m.page_no)},{float(m.x_pdf)},{float(m.y_pdf)}\n"
                    )

            messagebox.showinfo("Export CSV", f"CSV exported to:\n{csv_path}")
        except Exception as e:
            self._show_unexpected("Failed to export CSV", e)

    def prev_page(self) -> None:
        # Deprecated in continuous mode: retained for compatibility.
        self.on_page_up_key(None)  # type: ignore[arg-type]

    def next_page(self) -> None:
        # Deprecated in continuous mode: retained for compatibility.
        self.on_page_down_key(None)  # type: ignore[arg-type]

    def on_arrow_left(self, event: tk.Event) -> None:
        # Left/right no longer page-switch in continuous mode.
        return

    def on_arrow_right(self, event: tk.Event) -> None:
        # Left/right no longer page-switch in continuous mode.
        return

    def zoom_in(self) -> None:
        try:
            if self.doc is None:
                return
            new_zoom = min(self.max_zoom, self.zoom + 0.1)
            if abs(new_zoom - self.zoom) < 1e-9:
                return
            self.zoom = new_zoom
            self.render_current_page()
        except Exception as e:
            self._show_unexpected("Failed to zoom in", e)

    def zoom_out(self) -> None:
        try:
            if self.doc is None:
                return
            new_zoom = max(self.min_zoom, self.zoom - 0.1)
            if abs(new_zoom - self.zoom) < 1e-9:
                return
            self.zoom = new_zoom
            self.render_current_page()
        except Exception as e:
            self._show_unexpected("Failed to zoom out", e)

    def _get_viewport_canvas_metrics(self) -> Tuple[float, float, float, float]:
        vw = max(1, float(self.canvas.winfo_width()))
        vh = max(1, float(self.canvas.winfo_height()))
        x_left = float(self.canvas.canvasx(0))
        y_top = float(self.canvas.canvasy(0))
        return x_left, y_top, vw, vh

    def _scroll_canvas_by_pixels(self, dx_pixels: float, dy_pixels: float) -> None:
        if self.pix_width <= 0 or self.pix_height <= 0:
            return
        x_left, y_top, vw, vh = self._get_viewport_canvas_metrics()
        max_left = max(0.0, float(self.pix_width) - vw)
        max_top = max(0.0, float(self.pix_height) - vh)
        new_x_left = max(0.0, min(max_left, x_left + dx_pixels))
        new_y_top = max(0.0, min(max_top, y_top + dy_pixels))
        self.canvas.xview_moveto(new_x_left / max(1.0, float(self.pix_width)))
        self.canvas.yview_moveto(new_y_top / max(1.0, float(self.pix_height)))

    def _on_mouse_wheel_global(self, event: tk.Event) -> None:
        if self.doc is None:
            return
        self.on_mouse_wheel(event)

    def on_mouse_wheel(self, event: tk.Event) -> None:
        try:
            if self.doc is None:
                return
            delta = int(getattr(event, "delta", 0))
            if delta == 0:
                return
            units = int(delta / 120)
            if units == 0:
                units = 1 if delta > 0 else -1
            _, _, vw, vh = self._get_viewport_canvas_metrics()
            step_v = max(40, int(vh * 0.14))
            step_h = max(40, int(vw * 0.14))
            if (int(getattr(event, "state", 0)) & 0x0001) != 0:
                self._scroll_canvas_by_pixels(dx_pixels=-units * step_h, dy_pixels=0.0)
            else:
                self._scroll_canvas_by_pixels(dx_pixels=0.0, dy_pixels=-units * step_v)
        except Exception as e:
            self._show_unexpected("Failed to handle mouse wheel", e)

    def on_mouse_wheel_linux(self, event: tk.Event) -> None:
        try:
            if self.doc is None:
                return
            units = 1 if int(getattr(event, "num", 0)) == 4 else -1
            _, _, vw, vh = self._get_viewport_canvas_metrics()
            step_v = max(40, int(vh * 0.14))
            step_h = max(40, int(vw * 0.14))
            if (int(getattr(event, "state", 0)) & 0x0001) != 0:
                self._scroll_canvas_by_pixels(dx_pixels=-units * step_h, dy_pixels=0.0)
            else:
                self._scroll_canvas_by_pixels(dx_pixels=0.0, dy_pixels=-units * step_v)
        except Exception as e:
            self._show_unexpected("Failed to handle mouse wheel", e)

    def on_page_down_key(self, event: tk.Event) -> None:
        try:
            if self.doc is None:
                return
            if self.root.focus_get() == self.go_to_marker_entry:
                return
            _, _, _, vh = self._get_viewport_canvas_metrics()
            self._scroll_canvas_by_pixels(dx_pixels=0.0, dy_pixels=int(vh * 0.9))
        except Exception as e:
            self._show_unexpected("Failed to handle PageDown", e)

    def on_page_up_key(self, event: tk.Event) -> None:
        try:
            if self.doc is None:
                return
            if self.root.focus_get() == self.go_to_marker_entry:
                return
            _, _, _, vh = self._get_viewport_canvas_metrics()
            self._scroll_canvas_by_pixels(dx_pixels=0.0, dy_pixels=-int(vh * 0.9))
        except Exception as e:
            self._show_unexpected("Failed to handle PageUp", e)

    def on_home_key(self, event: tk.Event) -> None:
        try:
            if self.doc is None:
                return
            if self.root.focus_get() == self.go_to_marker_entry:
                return
            self.canvas.yview_moveto(0.0)
        except Exception as e:
            self._show_unexpected("Failed to handle Home key", e)

    def on_end_key(self, event: tk.Event) -> None:
        try:
            if self.doc is None:
                return
            if self.root.focus_get() == self.go_to_marker_entry:
                return
            self.canvas.yview_moveto(1.0)
        except Exception as e:
            self._show_unexpected("Failed to handle End key", e)

    def save_markers_json(self) -> None:
        if self.doc is None or not self.filepath:
            messagebox.showerror("Error", "No PDF is open.")
            return

        json_path = self.get_markers_json_path()
        tmp_path = self.get_markers_tmp_json_path()
        if not json_path:
            messagebox.showerror("Error", "Could not determine markers JSON path.")
            return

        try:
            if not tmp_path:
                raise RuntimeError("Could not determine markers temp JSON path.")
            data = self._snapshot_markers_json_data()
            self._safe_write_json_to_tmp_and_replace(json_path=json_path, tmp_path=tmp_path, data=data)
            self._set_status("Saved")

            messagebox.showinfo("Success", f"Markers saved to:\n{json_path}")
        except Exception as e:
            self._set_status("Error saving")
            messagebox.showerror("Save Error", f"Failed to save markers JSON:\n{e}")

    def _collect_marker_tuples_for_pdf_export(self) -> List[Tuple[int, float, float, int]]:
        """(page_no 1-based, x_pdf, y_pdf, marker_no) for embedding in output PDF."""
        with self._markers_lock:
            items: List[Tuple[int, float, float, int]] = []
            for pno in sorted(self.markers_by_page.keys()):
                for m in self.markers_by_page[pno]:
                    items.append((m.page_no, float(m.x_pdf), float(m.y_pdf), int(m.marker_no)))
        return items

    def _apply_markers_to_fitz_doc(
        self, doc: fitz.Document, items: List[Tuple[int, float, float, int]]
    ) -> None:
        """Draw black square and white 3-digit label at each marker (matches on-screen style)."""
        npages = len(doc)
        half = 4.0
        for page_no, x_pdf, y_pdf, marker_no in items:
            if page_no < 1 or page_no > npages:
                continue
            page = doc[page_no - 1]
            r = fitz.Rect(x_pdf - half, y_pdf - half, x_pdf + half, y_pdf + half)
            page.draw_rect(r, color=(0, 0, 0), fill=(0, 0, 0), width=0)
            label = f"{marker_no:03d}"
            tw = 22.0
            label_rect = fitz.Rect(x_pdf - tw, y_pdf + half + 0.5, x_pdf + tw, y_pdf + half + 14.0)
            page.insert_textbox(
                label_rect,
                label,
                fontsize=9,
                fontname="helv",
                color=(1, 1, 1),
                align=fitz.TEXT_ALIGN_CENTER,
            )

    def save_pdf_with_markers(self) -> None:
        if self.doc is None or not self.filepath:
            messagebox.showerror("Error", "No PDF is open.")
            return

        items = self._collect_marker_tuples_for_pdf_export()
        base = os.path.splitext(os.path.basename(self.filepath))[0]
        initial = f"{base}_marked.pdf"
        folder = os.path.dirname(self.filepath)
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialdir=folder,
            initialfile=initial,
            title="Save PDF with markers",
        )
        if not path:
            return

        if os.path.normpath(path) == os.path.normpath(self.filepath):
            if not messagebox.askyesno(
                "Overwrite PDF?",
                "You chose the same file you opened. It will be replaced with a version that includes the markers.\n\nContinue?",
            ):
                return

        try:
            pdf_bytes = self.doc.write()
            out_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                self._apply_markers_to_fitz_doc(out_doc, items)
                out_doc.save(path, garbage=4, deflate=True)
            finally:
                out_doc.close()
            self._set_status("PDF saved")
            messagebox.showinfo("Success", f"PDF saved to:\n{path}")
        except Exception as e:
            self._set_status("Error saving PDF")
            messagebox.showerror("Save PDF Error", f"Failed to save PDF:\n{e}")


def main() -> None:
    root = tk.Tk()
    root.geometry("1000x750")
    app = PDFMarkerApp(root)

    pdf_arg: Optional[str] = None
    for arg in sys.argv[1:]:
        if arg.lower().endswith(".pdf") and os.path.isfile(arg):
            pdf_arg = os.path.abspath(arg)
            break
    if pdf_arg:
        # Defer until Tk and window exist (needed for macOS .app / Open With).
        root.after(200, lambda p=pdf_arg: app.open_pdf_path(p))

    root.mainloop()


if __name__ == "__main__":
    main()
