from __future__ import annotations

from pathlib import Path
import queue
import tempfile
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image

try:
    import customtkinter as ctk
except Exception as exc:  # pragma: no cover
    raise RuntimeError("customtkinter is required. Run: pip install -r requirements.txt") from exc

from .profiles import PROFILE_LABELS, get_profile
from .models import EnhancementSettings
from .worker import process_pdf, create_preview


class UltraBookApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("UltraBook PDF Clarity Studio")
        self.geometry("1280x820")
        # Keep the app usable on smaller laptop screens.
        # The settings column is scrollable, so controls will not be clipped.
        self.minsize(980, 620)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.profile_var = tk.StringVar(value="Supreme Text Clarity - 600 DPI")
        self.dpi_var = tk.StringVar(value="600")
        self.mode_var = tk.StringVar(value="auto")
        self.ocr_var = tk.StringVar(value="none")
        self.lang_var = tk.StringVar(value="eng")
        self.page_preview_var = tk.StringVar(value="1")

        self.deskew_var = tk.BooleanVar(value=True)
        self.border_var = tk.BooleanVar(value=True)
        self.binarize_var = tk.BooleanVar(value=True)
        self.speckle_var = tk.BooleanVar(value=True)
        self.repair_var = tk.BooleanVar(value=True)
        self.keep_color_var = tk.BooleanVar(value=True)

        self.bg_strength = tk.DoubleVar(value=1.0)
        self.shadow_strength = tk.DoubleVar(value=1.0)
        self.denoise_strength = tk.DoubleVar(value=0.70)
        self.sharpen_strength = tk.DoubleVar(value=0.95)
        self.contrast_strength = tk.DoubleVar(value=0.95)

        self.msg_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.preview_image_ref = None

        self._build_ui()
        self.after(120, self._poll_queue)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Use a scrollable settings panel.
        # A normal CTkFrame clips the lower controls on smaller screens,
        # which makes the page feel like it is not scrolling.
        left = ctk.CTkScrollableFrame(self, corner_radius=18, width=390)
        left.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        left.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(left, text="UltraBook PDF\nClarity Studio", font=ctk.CTkFont(size=26, weight="bold"), justify="left")
        title.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
        subtitle = ctk.CTkLabel(left, text="Maximum-quality scanned-book PDF restoration", text_color="#b8c7d9", justify="left")
        subtitle.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))

        self._file_picker(left, 2, "Input PDF", self.input_var, self.browse_input)
        self._file_picker(left, 3, "Output PDF", self.output_var, self.browse_output)

        ctk.CTkLabel(left, text="Quality Profile", font=ctk.CTkFont(weight="bold")).grid(row=4, column=0, sticky="w", padx=18, pady=(12, 4))
        profile = ctk.CTkOptionMenu(left, values=list(PROFILE_LABELS.keys()), variable=self.profile_var, command=self.apply_profile)
        profile.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 8))

        row = ctk.CTkFrame(left, fg_color="transparent")
        row.grid(row=6, column=0, sticky="ew", padx=18, pady=4)
        row.grid_columnconfigure((0, 1), weight=1)
        self._option(row, 0, "DPI", self.dpi_var, ["300", "400", "500", "600"])
        self._option(row, 1, "Mode", self.mode_var, ["auto", "bilevel", "grayscale", "color"])

        toggles = ctk.CTkFrame(left, corner_radius=14)
        toggles.grid(row=7, column=0, sticky="ew", padx=18, pady=(10, 8))
        toggles.grid_columnconfigure((0, 1), weight=1)
        self._check(toggles, 0, 0, "Deskew", self.deskew_var)
        self._check(toggles, 0, 1, "Clean borders", self.border_var)
        self._check(toggles, 1, 0, "Binarize text", self.binarize_var)
        self._check(toggles, 1, 1, "Remove speckles", self.speckle_var)
        self._check(toggles, 2, 0, "Repair strokes", self.repair_var)
        self._check(toggles, 2, 1, "Keep color pages", self.keep_color_var)

        sliders = ctk.CTkFrame(left, corner_radius=14)
        sliders.grid(row=8, column=0, sticky="ew", padx=18, pady=8)
        sliders.grid_columnconfigure(0, weight=1)
        self._slider(sliders, 0, "Background flattening", self.bg_strength)
        self._slider(sliders, 1, "Shadow removal", self.shadow_strength)
        self._slider(sliders, 2, "Denoise", self.denoise_strength)
        self._slider(sliders, 3, "Sharpen", self.sharpen_strength)
        self._slider(sliders, 4, "Local contrast", self.contrast_strength)

        ocr = ctk.CTkFrame(left, corner_radius=14)
        ocr.grid(row=9, column=0, sticky="ew", padx=18, pady=8)
        ocr.grid_columnconfigure((0, 1), weight=1)
        self._option(ocr, 0, "OCR", self.ocr_var, ["none", "ocrmypdf", "tesseract"])
        lang_frame = ctk.CTkFrame(ocr, fg_color="transparent")
        lang_frame.grid(row=0, column=1, sticky="ew", padx=6, pady=6)
        ctk.CTkLabel(lang_frame, text="Language").pack(anchor="w")
        ctk.CTkEntry(lang_frame, textvariable=self.lang_var).pack(fill="x")

        buttons = ctk.CTkFrame(left, fg_color="transparent")
        buttons.grid(row=10, column=0, sticky="ew", padx=18, pady=(10, 18))
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(buttons, text="Preview Page", command=self.preview_page, height=42).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(buttons, text="Start Enhancement", command=self.start_processing, height=42, fg_color="#1f9d55", hover_color="#16803f").grid(row=0, column=1, sticky="ew", padx=(6, 0))

        right = ctk.CTkFrame(self, corner_radius=18)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 14), pady=14)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        right.grid_rowconfigure(4, weight=0)

        topbar = ctk.CTkFrame(right, fg_color="transparent")
        topbar.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        topbar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(topbar, text="Preview page:").grid(row=0, column=0, padx=(0, 8))
        ctk.CTkEntry(topbar, width=80, textvariable=self.page_preview_var).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(topbar, text="Before / After preview is lower-DPI for speed. Full output uses selected DPI.", text_color="#b8c7d9").grid(row=0, column=2, sticky="e")

        self.preview_label = ctk.CTkLabel(right, text="Select a PDF and click Preview Page", fg_color="#101820", corner_radius=14)
        self.preview_label.grid(row=1, column=0, sticky="nsew", padx=18, pady=8)

        self.progress = ctk.CTkProgressBar(right)
        self.progress.grid(row=2, column=0, sticky="ew", padx=18, pady=(8, 4))
        self.progress.set(0)
        self.status_label = ctk.CTkLabel(right, text="Idle", anchor="w", text_color="#b8c7d9")
        self.status_label.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 8))

        ctk.CTkLabel(right, text="Processing Log", font=ctk.CTkFont(weight="bold")).grid(row=4, column=0, sticky="w", padx=18, pady=(8, 2))
        self.log_box = ctk.CTkTextbox(right, height=160)
        self.log_box.grid(row=5, column=0, sticky="ew", padx=18, pady=(2, 18))
        self.log("Ready. Use Supreme Text Clarity for the strongest scanned-book cleanup.")

    def _file_picker(self, parent, row, label, variable, command):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", padx=18, pady=6)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkEntry(frame, textvariable=variable).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ctk.CTkButton(frame, text="Browse", width=90, command=command).grid(row=1, column=1, padx=(8, 0), pady=(4, 0))

    def _option(self, parent, col, label, variable, values):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=col, sticky="ew", padx=6, pady=6)
        ctk.CTkLabel(frame, text=label).pack(anchor="w")
        ctk.CTkOptionMenu(frame, variable=variable, values=values).pack(fill="x")

    def _check(self, parent, row, col, text, variable):
        ctk.CTkCheckBox(parent, text=text, variable=variable).grid(row=row, column=col, sticky="w", padx=10, pady=8)

    def _slider(self, parent, row, label, variable):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", padx=10, pady=(8 if row == 0 else 4, 4))
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=label).grid(row=0, column=0, sticky="w")
        value_label = ctk.CTkLabel(frame, text=f"{variable.get():.2f}", width=48)
        value_label.grid(row=0, column=1, sticky="e")
        slider = ctk.CTkSlider(frame, from_=0.0, to=1.5, variable=variable, command=lambda v, lab=value_label: lab.configure(text=f"{float(v):.2f}"))
        slider.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))

    def browse_input(self):
        p = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not p:
            return
        self.input_var.set(p)
        out = Path(p).with_name(Path(p).stem + "_ultrabook_enhanced.pdf")
        self.output_var.set(str(out))

    def browse_output(self):
        p = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if p:
            self.output_var.set(p)

    def apply_profile(self, _value=None):
        try:
            s = get_profile(self.profile_var.get())
        except Exception:
            return
        self.dpi_var.set(str(s.dpi))
        self.mode_var.set(s.output_mode)
        self.deskew_var.set(s.auto_deskew)
        self.border_var.set(s.clean_borders)
        self.binarize_var.set(s.binarize_text_pages)
        self.speckle_var.set(s.remove_speckles)
        self.repair_var.set(s.repair_broken_strokes)
        self.keep_color_var.set(s.keep_color_pages)
        self.bg_strength.set(s.background_strength)
        self.shadow_strength.set(s.shadow_removal_strength)
        self.denoise_strength.set(s.denoise_strength)
        self.sharpen_strength.set(s.sharpen_strength)
        self.contrast_strength.set(s.contrast_strength)
        self.log(f"Applied profile: {s.profile_name}")

    def collect_settings(self) -> EnhancementSettings:
        base = get_profile(self.profile_var.get())
        base.dpi = int(self.dpi_var.get())
        base.output_mode = self.mode_var.get()
        base.ocr_mode = self.ocr_var.get()
        base.ocr_language = self.lang_var.get().strip() or "eng"
        base.auto_deskew = bool(self.deskew_var.get())
        base.clean_borders = bool(self.border_var.get())
        base.binarize_text_pages = bool(self.binarize_var.get())
        base.remove_speckles = bool(self.speckle_var.get())
        base.repair_broken_strokes = bool(self.repair_var.get())
        base.keep_color_pages = bool(self.keep_color_var.get())
        base.background_strength = float(self.bg_strength.get())
        base.shadow_removal_strength = float(self.shadow_strength.get())
        base.denoise_strength = float(self.denoise_strength.get())
        base.sharpen_strength = float(self.sharpen_strength.get())
        base.contrast_strength = float(self.contrast_strength.get())
        return base.normalized()

    def log(self, message: str):
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")

    def _validate_paths(self) -> tuple[Path, Path] | None:
        inp = Path(self.input_var.get().strip())
        out = Path(self.output_var.get().strip())
        if not inp.exists() or inp.suffix.lower() != ".pdf":
            messagebox.showerror("Input PDF", "Choose a valid input PDF file.")
            return None
        if not out.name.lower().endswith(".pdf"):
            messagebox.showerror("Output PDF", "Output file must end with .pdf")
            return None
        return inp, out

    def preview_page(self):
        paths = self._validate_paths()
        if not paths:
            return
        inp, _out = paths
        try:
            page = int(self.page_preview_var.get())
        except ValueError:
            page = 1
        settings = self.collect_settings()
        temp = Path(tempfile.mkdtemp(prefix="ultrabook_preview_"))
        self.progress.set(0.05)
        self.status_label.configure(text="Creating preview...")
        self.log(f"Previewing page {page} at preview DPI {min(settings.dpi, 300)}...")

        def task():
            try:
                before, after, side = create_preview(inp, page, settings, temp)
                self.msg_queue.put(("preview", side))
            except Exception:
                self.msg_queue.put(("error", traceback.format_exc()))

        threading.Thread(target=task, daemon=True).start()

    def start_processing(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Processing", "A job is already running.")
            return
        paths = self._validate_paths()
        if not paths:
            return
        inp, out = paths
        settings = self.collect_settings()
        self.progress.set(0)
        self.log(f"Starting full enhancement: {inp.name}")
        self.log(f"Profile={settings.profile_name}, DPI={settings.dpi}, mode={settings.output_mode}, OCR={settings.ocr_mode}")

        def progress(value: float, message: str):
            self.msg_queue.put(("progress", (value, message)))

        def task():
            try:
                result = process_pdf(inp, out, settings, progress=progress)
                self.msg_queue.put(("done", result))
            except Exception:
                self.msg_queue.put(("error", traceback.format_exc()))

        self.worker_thread = threading.Thread(target=task, daemon=True)
        self.worker_thread.start()

    def _show_preview(self, image_path: Path):
        img = Image.open(image_path).convert("RGB")
        max_w = max(500, self.preview_label.winfo_width() - 30)
        max_h = max(360, self.preview_label.winfo_height() - 30)
        img.thumbnail((max_w, max_h), Image.LANCZOS)
        self.preview_image_ref = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        self.preview_label.configure(image=self.preview_image_ref, text="")
        self.progress.set(1)
        self.status_label.configure(text=f"Preview created: {image_path}")
        self.log(f"Preview created: {image_path}")

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "progress":
                    value, message = payload
                    self.progress.set(float(value))
                    self.status_label.configure(text=str(message))
                    self.log(str(message))
                elif kind == "preview":
                    self._show_preview(Path(payload))
                elif kind == "done":
                    result = payload
                    self.progress.set(1)
                    msg = f"Done. Enhanced PDF: {result.output_pdf}"
                    if result.searchable_pdf:
                        msg += f" | Searchable: {result.searchable_pdf}"
                    self.status_label.configure(text=msg)
                    self.log(msg)
                    if result.warnings:
                        for w in result.warnings:
                            self.log("Warning: " + w)
                    messagebox.showinfo("Finished", msg)
                elif kind == "error":
                    self.progress.set(0)
                    self.status_label.configure(text="Error")
                    self.log("ERROR:\n" + str(payload))
                    messagebox.showerror("Error", str(payload)[-3500:])
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)


def main():
    app = UltraBookApp()
    app.mainloop()
