"""Herramientas adicionales: unir PDFs, exportar a imágenes y procesar en lote."""
import os
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from . import core
from .core import PlanError
from .i18n import t
from .theme import C, font, icon
from .widgets import Dialog, FileList, Tooltip, button, card, checkbox, entry, label, segmented, set_enabled
from .split_view import acortar_texto


def view_header(parent, title, subtitle):
    cabecera = ctk.CTkFrame(parent, fg_color="transparent")
    label(cabecera, title, 22, "bold", anchor="w").pack(fill="x")
    label(cabecera, subtitle, 13, color="muted", anchor="w").pack(fill="x", pady=(2, 0))
    return cabecera


def file_toolbar(parent, on_add, on_clear):
    barra = ctk.CTkFrame(parent, fg_color="transparent")
    button(barra, t("add_files"), "add", variant="primary", size="sm", command=on_add).pack(side="left")
    button(barra, t("clear"), "delete", variant="ghost", size="sm", command=on_clear).pack(side="left", padx=(6, 0))
    resumen = label(barra, "", 12, color="muted")
    resumen.pack(side="right")
    return barra, resumen


def ask_pdfs(app):
    return list(filedialog.askopenfilenames(parent=app, filetypes=[(t("filetype_pdf"), "*.pdf")]))


# ----------------------------------------------------
# Unir
# ----------------------------------------------------
class MergeView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.var_bookmark = ctk.BooleanVar(value=True)
        self.var_compress = ctk.BooleanVar(value=False)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        view_header(self, t("merge_title"), t("merge_subtitle")).grid(row=0, column=0, sticky="ew", pady=(0, 14))

        tarjeta = card(self)
        tarjeta.grid(row=1, column=0, sticky="nsew")
        barra, self.summary = file_toolbar(tarjeta, lambda: self.files.add_files(ask_pdfs(app)), lambda: self.files.clear())
        barra.pack(fill="x", padx=14, pady=(14, 10))
        self.files = FileList(tarjeta, app, on_change=self._on_change)
        self.files.pack(fill="both", expand=True, padx=14)

        pie = ctk.CTkFrame(tarjeta, fg_color="transparent")
        pie.pack(fill="x", padx=14, pady=14)
        checkbox(pie, t("merge_bookmark"), self.var_bookmark, tooltip=t("merge_bookmark_tip")).pack(side="left", padx=(0, 14))
        checkbox(pie, t("opt_compress"), self.var_compress, tooltip=t("opt_compress_tip")).pack(side="left")
        self.merge_btn = button(pie, t("merge_button"), "merge", variant="success", size="lg", width=180, command=self.merge)
        self.merge_btn.pack(side="right")
        self._on_change()

    def _on_change(self):
        n = len(self.files.items)
        self.summary.configure(text=f"{t('files_count', n=n)} · {t('pages_count', n=self.files.total_pages())}" if n else "")
        set_enabled(self.merge_btn, n >= 2)

    def handle_drop(self, rutas):
        self.files.add_files(rutas)

    def merge(self):
        rutas = self.files.paths()
        if len(rutas) < 2 or self.app.busy:
            return
        salida = filedialog.asksaveasfilename(parent=self.app, defaultextension=".pdf", initialfile=t("merge_default_name"),
                                              initialdir=os.path.dirname(rutas[0]), filetypes=[(t("filetype_pdf"), "*.pdf")])
        if not salida:
            return
        if os.path.normcase(os.path.abspath(salida)) in {os.path.normcase(os.path.abspath(r)) for r in rutas}:
            Dialog.alert(self.app, t("merge_same_file_title"), t("merge_same_file_message"))
            return
        opciones = {"bookmark_per_file": bool(self.var_bookmark.get()), "compress": bool(self.var_compress.get())}

        def al_terminar(resultado):
            ok, errores, cancelado = resultado
            if cancelado:
                self.app.toast(t("merge_cancelled"), "info")
            elif ok and not errores:
                self.app.toast(t("merge_done", n=len(rutas)), "success",
                               action=(t("open_folder"), lambda: self.app.open_folder(os.path.dirname(salida))))
            else:
                Dialog.alert(self.app, t("done_with_errors") if ok else t("merge_failed"),
                             t("problems_found"), detail="\n".join(errores))

        passwords = self.app.passwords_for(rutas)
        self.app.run_task(t("merge_progress"), lambda log, cancel: core.merge_pdfs(rutas, salida, opciones, log, cancel, passwords),
                          al_terminar)


# ----------------------------------------------------
# Exportar a imágenes
# ----------------------------------------------------
# (clave de traducción, ppp)
CALIDADES = [("quality_low", 72), ("quality_medium", 150), ("quality_high", 300)]


class ImagesView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.source = ""
        self.dest = ""
        self.dest_is_auto = True
        self._job = None
        self._cancel = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        view_header(self, t("images_title"), t("images_subtitle")).grid(row=0, column=0, sticky="ew", pady=(0, 14))

        tarjeta = card(self)
        tarjeta.grid(row=1, column=0, sticky="new")
        tarjeta.grid_columnconfigure(1, weight=1)

        def fila(n, texto):
            label(tarjeta, texto, 13, "bold", anchor="w").grid(row=n, column=0, sticky="w", padx=(18, 16), pady=10)

        fila(0, t("images_file"))
        marco = ctk.CTkFrame(tarjeta, fg_color="transparent")
        marco.grid(row=0, column=1, sticky="ew", padx=(0, 18), pady=(14, 10))
        self.source_label = label(marco, t("no_pdf_selected"), 13, color="muted", anchor="w")
        self.source_label.pack(side="left", fill="x", expand=True)
        button(marco, t("choose"), "open_file", size="sm", command=self.choose_source).pack(side="right")
        self.use_current_btn = button(marco, t("images_use_current"), variant="ghost", size="sm", command=self.use_current)
        self.use_current_btn.pack(side="right", padx=(0, 6))

        fila(1, t("images_pages"))
        self.pages_entry = entry(tarjeta, t("images_pages_placeholder"))
        self.pages_entry.grid(row=1, column=1, sticky="ew", padx=(0, 18), pady=10)

        fila(2, t("images_quality"))
        self.calidades = {t(clave, dpi=ppp): ppp for clave, ppp in CALIDADES}
        self.quality = segmented(tarjeta, list(self.calidades))
        self.quality.set(list(self.calidades)[1])
        self.quality.grid(row=2, column=1, sticky="w", padx=(0, 18), pady=10)

        fila(3, t("images_format"))
        self.format = segmented(tarjeta, ["PNG", "JPG"])
        self.format.set("PNG")
        self.format.grid(row=3, column=1, sticky="w", padx=(0, 18), pady=10)

        fila(4, t("destination"))
        marco = ctk.CTkFrame(tarjeta, fg_color="transparent")
        marco.grid(row=4, column=1, sticky="ew", padx=(0, 18), pady=(10, 14))
        self.dest_label = label(marco, t("dest_auto"), 13, color="muted", anchor="w")
        self.dest_label.pack(side="left", fill="x", expand=True)
        self.dest_tooltip = Tooltip(self.dest_label, "")
        button(marco, t("change"), size="sm", command=self.choose_dest).pack(side="right")

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self.status = label(pie, "", 12, color="muted", anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        self.export_btn = button(pie, t("images_button"), "image", variant="success", size="lg", width=200, command=self.export)
        self.export_btn.pack(side="right")
        self.cancel_btn = button(pie, t("cancel"), variant="secondary", size="lg", command=self.cancel)
        self.progress = ctk.CTkProgressBar(self, height=8, corner_radius=4, progress_color=C["accent"], fg_color=C["surface_alt"])

    def on_show(self):
        split = self.app.views["split"]
        set_enabled(self.use_current_btn, bool(split.pdf_path))
        if not self.source and split.pdf_path:
            self.use_current()

    def handle_drop(self, rutas):
        pdfs = [r for r in rutas if r.lower().endswith(".pdf")]
        if pdfs:
            self._set_source(pdfs[0])

    def use_current(self):
        if self.app.views["split"].pdf_path:
            self._set_source(self.app.views["split"].pdf_path)

    def choose_source(self):
        ruta = filedialog.askopenfilename(parent=self.app, filetypes=[(t("filetype_pdf"), "*.pdf")])
        if ruta:
            self._set_source(ruta)

    def _set_source(self, ruta):
        self.source = os.path.normpath(ruta)
        self.source_label.configure(text=acortar_texto(os.path.basename(self.source), 44), text_color=C["text"])
        if self.dest_is_auto:
            base = os.path.splitext(os.path.basename(self.source))[0]
            self._set_dest(os.path.join(os.path.dirname(self.source), f"{base}_{t('suffix_images')}"), auto=True)

    def choose_dest(self):
        carpeta = filedialog.askdirectory(parent=self.app)
        if carpeta:
            self._set_dest(carpeta, auto=False)

    def _set_dest(self, ruta, auto):
        self.dest = os.path.normpath(ruta)
        self.dest_is_auto = auto
        self.dest_label.configure(text=acortar_texto(self.dest, 50), text_color=C["text"])
        self.dest_tooltip.text = self.dest

    def export(self):
        if self.app.busy:
            return
        if not self.source:
            Dialog.alert(self.app, t("missing_pdf_title"), t("images_missing_pdf"), "info")
            return
        try:
            doc = self.app.open_fitz(self.source)  # Pide la contraseña si hace falta
            if doc is None:
                return
            texto = self.pages_entry.get().strip()
            if texto:
                paginas = [p for a, b in core.parse_ranges(texto, doc.page_count) for p in range(a - 1, b)]
            else:
                paginas = list(range(doc.page_count))
            os.makedirs(self.dest, exist_ok=True)
        except PlanError as e:
            Dialog.alert(self.app, t("images_check_pages"), str(e))
            return
        except Exception as e:
            Dialog.alert(self.app, t("images_failed"), str(e))
            return

        dpi = self.calidades[self.quality.get()]
        formato = self.format.get().lower()
        base = os.path.splitext(os.path.basename(self.source))[0]
        ancho = max(3, len(str(doc.page_count)))
        self._cancel = False
        self.app.busy = True
        self.export_btn.pack_forget()
        self.cancel_btn.pack(side="right")
        self.progress.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.progress.set(0)

        # Se renderiza de a una página por ciclo para que la interfaz siga respondiendo
        def paso(i=0):
            if self._cancel or i >= len(paginas):
                terminar(i)
                return
            n = paginas[i]
            try:
                pix = doc.load_page(n).get_pixmap(dpi=dpi, alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                ruta = os.path.join(self.dest, f"{base}_p{n + 1:0{ancho}d}.{formato}")
                if formato == "jpg":
                    img.save(ruta, "JPEG", quality=90)
                else:
                    img.save(ruta, "PNG", optimize=False)
            except Exception as e:
                doc.close()
                self._finish_ui()
                Dialog.alert(self.app, t("images_failed"), t("images_page_error", page=n + 1, error=e))
                return
            self.progress.set((i + 1) / len(paginas))
            self.status.configure(text=t("images_progress", page=n + 1, i=i + 1, total=len(paginas)))
            self._job = self.after(1, lambda: paso(i + 1))

        def terminar(hechas):
            doc.close()
            self._finish_ui()
            if self._cancel:
                self.app.toast(t("images_cancelled", n=hechas), "info")
            else:
                self.app.toast(t("images_done", n=hechas), "success",
                               action=(t("open_folder"), lambda: self.app.open_folder(self.dest)))

        paso()

    def _finish_ui(self):
        self.app.busy = False
        self._job = None
        self.cancel_btn.pack_forget()
        self.export_btn.pack(side="right")
        self.progress.grid_remove()
        self.status.configure(text="")

    def cancel(self):
        self._cancel = True


# ----------------------------------------------------
# Lote
# ----------------------------------------------------
class BatchView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.dest_root = ""
        self.var_dest_mode = ctk.StringVar(value="next")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        view_header(self, t("batch_title"), t("batch_subtitle")).grid(row=0, column=0, sticky="ew", pady=(0, 14))

        tarjeta = card(self)
        tarjeta.grid(row=1, column=0, sticky="nsew")
        barra, self.summary = file_toolbar(tarjeta, lambda: self.files.add_files(ask_pdfs(app)), lambda: self.files.clear())
        barra.pack(fill="x", padx=14, pady=(14, 10))
        self.files = FileList(tarjeta, app, on_change=self._on_change, reorderable=False)
        self.files.pack(fill="both", expand=True, padx=14)

        # Configuración que se va a aplicar (la de la pestaña Dividir)
        info = ctk.CTkFrame(tarjeta, fg_color=C["accent_soft"], corner_radius=10)
        info.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkLabel(info, text="", image=icon("info", 18, "accent_text")).pack(side="left", padx=(12, 10), pady=10)
        textos = ctk.CTkFrame(info, fg_color="transparent")
        textos.pack(side="left", fill="x", expand=True, pady=8)
        label(textos, t("batch_uses_split"), 12, color="accent_text", anchor="w").pack(fill="x")
        self.spec_label = label(textos, "", 13, "bold", anchor="w")
        self.spec_label.pack(fill="x")
        button(info, t("edit"), variant="ghost", size="sm", command=lambda: app.show_view("split")).pack(side="right", padx=10)

        destino = ctk.CTkFrame(tarjeta, fg_color="transparent")
        destino.pack(fill="x", padx=14, pady=(12, 0))
        label(destino, t("batch_save_in"), 13, "bold").pack(side="left", padx=(0, 12))
        radio = dict(variable=self.var_dest_mode, font=font(13), text_color=C["text"], fg_color=C["accent"],
                     hover_color=C["accent_hover"], radiobutton_width=18, radiobutton_height=18, command=self._on_change)
        ctk.CTkRadioButton(destino, text=t("batch_next_to_each"), value="next", **radio).pack(side="left", padx=(0, 14))
        ctk.CTkRadioButton(destino, text=t("batch_one_folder"), value="root", **radio).pack(side="left")
        self.root_btn = button(destino, t("choose"), "folder", size="sm", command=self.choose_root)
        self.root_btn.pack(side="left", padx=(8, 0))
        self.root_label = label(destino, "", 12, color="muted", anchor="w")
        self.root_label.pack(side="left", padx=(8, 0), fill="x", expand=True)

        pie = ctk.CTkFrame(tarjeta, fg_color="transparent")
        pie.pack(fill="x", padx=14, pady=14)
        label(pie, t("batch_folder_hint", suffix=t("suffix_split")), 12, color="muted").pack(side="left")
        self.run_btn = button(pie, t("batch_button"), "layers", variant="success", size="lg", width=200, command=self.run)
        self.run_btn.pack(side="right")
        self._on_change()

    def on_show(self):
        self._on_change()

    def handle_drop(self, rutas):
        self.files.add_files(rutas)

    def choose_root(self):
        carpeta = filedialog.askdirectory(parent=self.app)
        if carpeta:
            self.dest_root = os.path.normpath(carpeta)
            self.var_dest_mode.set("root")
            self._on_change()

    def _on_change(self):
        n = len(self.files.items)
        self.summary.configure(text=f"{t('files_count', n=n)} · {t('pages_count', n=self.files.total_pages())}" if n else "")
        self.spec_label.configure(text=core.describir_spec(self.app.views["split"].get_spec())
                                  if "split" in self.app.views else "")
        self.root_label.configure(text=acortar_texto(self.dest_root, 40) if self.dest_root else "")
        self.run_btn.configure(text=t("batch_button_n", n=n) if n else t("batch_button"))
        set_enabled(self.run_btn, n > 0)

    def run(self):
        rutas = self.files.paths()
        if not rutas or self.app.busy:
            return
        split = self.app.views["split"]
        spec = split.get_spec()
        # Validación básica de la configuración (los rangos se validan contra cada PDF al procesar)
        try:
            if spec["mode"] == "size":
                core.build_plan(spec, 1, [0])
            elif spec["mode"] == "keyword":
                if not spec.get("text"):
                    raise PlanError(t("err_keyword_empty"))
            else:
                core.build_plan(spec, 10 ** 6)
        except PlanError as e:
            Dialog.alert(self.app, t("check_config"), t("batch_invalid_config", error=e))
            return
        raiz = None
        if self.var_dest_mode.get() == "root":
            if not self.dest_root:
                Dialog.alert(self.app, t("batch_missing_folder_title"), t("batch_missing_folder"), "info")
                return
            raiz = self.dest_root
        opciones = split.get_options()

        def al_terminar(resultado):
            generados, errores, cancelado, carpetas = resultado
            abrir = raiz or (carpetas[0] if carpetas else None)
            accion = (t("open_folder"), lambda: self.app.open_folder(abrir)) if abrir else None
            if cancelado:
                self.app.toast(t("batch_cancelled", n=generados), "info")
            elif not errores:
                self.app.toast(t("batch_done", pdfs=len(rutas), n=generados), "success", action=accion)
            else:
                Dialog.alert(self.app, t("batch_done_with_errors"), t("generated_with_problems", n=generados),
                             detail="\n".join(errores))

        passwords = self.app.passwords_for(rutas)
        self.app.run_task(t("batch_progress"),
                          lambda log, cancel: core.batch_split(rutas, spec, raiz, opciones, log, cancel, passwords), al_terminar)
