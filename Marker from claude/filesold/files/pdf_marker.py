import tkinter as tk
from tkinter import filedialog, messagebox
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import os
import math

MARKER_CHAR = "\u25A0"  # ■ U+25A0

class PDFMarkerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Marker Tool - ToFanari")
        self.root.configure(bg="#2b1a1a")
        
        self.doc = None
        self.filepath = None
        self.current_page = 0
        self.zoom = 1.5
        self.markers = {}
        self.photo = None

        # Toolbar
        toolbar = tk.Frame(root, bg="#4a1c1c", pady=6)
        toolbar.pack(fill=tk.X)

        tk.Button(toolbar, text="📂 Άνοιγμα PDF", command=self.open_pdf,
                  bg="#8b1a1a", fg="white", font=("Arial", 11, "bold"),
                  padx=10).pack(side=tk.LEFT, padx=5)

        tk.Button(toolbar, text="💾 Αποθήκευση", command=self.save_pdf,
                  bg="#1a5c1a", fg="white", font=("Arial", 11, "bold"),
                  padx=10).pack(side=tk.LEFT, padx=5)

        tk.Button(toolbar, text="◀ Προηγ.", command=self.prev_page,
                  bg="#3a3a6a", fg="white", font=("Arial", 11)).pack(side=tk.LEFT, padx=5)

        tk.Button(toolbar, text="▶ Επόμ.", command=self.next_page,
                  bg="#3a3a6a", fg="white", font=("Arial", 11)).pack(side=tk.LEFT, padx=5)

        self.page_label = tk.Label(toolbar, text="Σελίδα: -", bg="#4a1c1c",
                                   fg="white", font=("Arial", 11))
        self.page_label.pack(side=tk.LEFT, padx=10)

        tk.Button(toolbar, text="↩ Αναίρεση", command=self.undo_last,
                  bg="#6a4a1a", fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)

        self.marker_label = tk.Label(toolbar, text="■ markers: 0", bg="#4a1c1c",
                                     fg="#FFD700", font=("Arial", 11, "bold"))
        self.marker_label.pack(side=tk.RIGHT, padx=10)

        # Info
        info = tk.Label(root,
                        text="👆 Αριστερό κλίκ = προσθήκη ■    |    🖱️ Δεξί κλίκ = διαγραφή ■",
                        bg="#2b1a1a", fg="#FFD700", font=("Arial", 11))
        info.pack(pady=4)

        # Canvas
        frame = tk.Frame(root, bg="#2b1a1a")
        frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(frame, bg="#1a1a1a", cursor="crosshair")
        scrollbar_y = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self.canvas.yview)
        scrollbar_x = tk.Scrollbar(root, orient=tk.HORIZONTAL, command=self.canvas.xview)

        self.canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_x.pack(fill=tk.X)

        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Button-3>", self.on_right_click)

    def open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if path:
            self.doc = fitz.open(path)
            self.filepath = path
            self.current_page = 0
            self.markers = {}
            self.render_page()

    def render_page(self):
        if not self.doc:
            return
        page = self.doc[self.current_page]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.configure(scrollregion=(0, 0, pix.width, pix.height))

        # Draw existing markers
        if self.current_page in self.markers:
            for i, (px, py) in enumerate(self.markers[self.current_page]):
                cx = px * self.zoom
                cy = py * self.zoom
                self.canvas.create_text(cx, cy, text="■", fill="#8b0000",
                                        font=("Arial", 18, "bold"), tags=f"marker_{i}")

        total = self.doc.page_count
        self.page_label.config(text=f"Σελίδα: {self.current_page+1} / {total}")
        self.update_marker_count()

    def on_left_click(self, event):
        if not self.doc:
            return
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        pdf_x = canvas_x / self.zoom
        pdf_y = canvas_y / self.zoom

        if self.current_page not in self.markers:
            self.markers[self.current_page] = []
        self.markers[self.current_page].append((pdf_x, pdf_y))

        self.canvas.create_text(canvas_x, canvas_y, text="■", fill="#8b0000",
                                font=("Arial", 18, "bold"))
        self.update_marker_count()

    def on_right_click(self, event):
        """Δεξί κλίκ - διαγραφή πλησιέστερου marker"""
        if not self.doc:
            return
        if self.current_page not in self.markers or not self.markers[self.current_page]:
            return

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        pdf_x = canvas_x / self.zoom
        pdf_y = canvas_y / self.zoom

        # Βρες τον πλησιέστερο marker
        markers = self.markers[self.current_page]
        min_dist = float('inf')
        min_idx = -1
        THRESHOLD = 20  # pixels σε PDF coords

        for i, (mx, my) in enumerate(markers):
            dist = math.sqrt((pdf_x - mx)**2 + (pdf_y - my)**2)
            if dist < min_dist:
                min_dist = dist
                min_idx = i

        if min_idx >= 0 and min_dist < THRESHOLD:
            markers.pop(min_idx)
            self.render_page()
            self.update_marker_count()
        else:
            # Κανένας marker κοντά
            pass

    def undo_last(self):
        if self.current_page in self.markers and self.markers[self.current_page]:
            self.markers[self.current_page].pop()
            self.render_page()

    def update_marker_count(self):
        total = sum(len(v) for v in self.markers.values())
        self.marker_label.config(text=f"■ markers: {total}")

    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            self.render_page()

    def next_page(self):
        if self.doc and self.current_page < self.doc.page_count - 1:
            self.current_page += 1
            self.render_page()

    def save_pdf(self):
        if not self.doc:
            messagebox.showerror("Σφάλμα", "Δεν έχει ανοιχτεί PDF!")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=os.path.basename(self.filepath).replace(".pdf", "_markers.pdf")
        )
        if not save_path:
            return

        font_paths = [
            "C:/Windows/Fonts/seguisym.ttf",
            "C:/Windows/Fonts/seguiemj.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/cour.ttf",
        ]
        
        font_path = None
        for fp in font_paths:
            if os.path.exists(fp):
                font_path = fp
                if "segui" in fp:
                    break

        for page_num, positions in self.markers.items():
            page = self.doc[page_num]
            for (px, py) in positions:
                point = fitz.Point(px, py)
                if font_path:
                    page.insert_text(
                        point,
                        MARKER_CHAR,
                        fontsize=14,
                        color=(0.54, 0, 0),
                        fontfile=font_path,
                        fontname="customfont"
                    )
                else:
                    page.insert_text(
                        point,
                        MARKER_CHAR,
                        fontsize=14,
                        color=(0.54, 0, 0),
                    )

        self.doc.save(save_path)

        # Επαλήθευση
        verify_doc = fitz.open(save_path)
        found = 0
        for page_num in range(verify_doc.page_count):
            page = verify_doc[page_num]
            instances = page.search_for(MARKER_CHAR)
            found += len(instances)
        verify_doc.close()

        messagebox.showinfo(
            "✅ Επιτυχία!",
            f"Αποθηκεύτηκε:\n{save_path}\n\n"
            f"■ markers που αναγνωρίζονται από το ToFanari app: {found}"
        )

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("900x700")
    app = PDFMarkerApp(root)
    root.mainloop()
