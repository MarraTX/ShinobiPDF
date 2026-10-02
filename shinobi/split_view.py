"""Vista principal: dividir un PDF."""
import json
import math
import os
import tkinter
from tkinter import filedialog

import customtkinter as ctk
import fitz  # PyMuPDF
from PIL import Image, ImageDraw

from . import APP_NAME, core, theme
from .core import PlanError
from .i18n import t
from .theme import C, CHAPTER_COLORS, font, icon, resolve
from .widgets import (Dialog, StepIndicator, ThumbnailStrip, Tooltip, button, card, checkbox, entry,
                      label, segmented, set_enabled)

# (modo, clave de traducción de su etiqueta)
MODOS = [("chapters", "mode_chapters"), ("every", "mode_every"), ("ranges", "mode_ranges"),
         ("size", "mode_size"), ("keyword", "mode_keyword")]


def acortar_texto(texto, max_chars=34):
    """Acorta un texto largo dejando el principio y el final visibles."""
    if len(texto) <= max_chars:
        return texto
    mitad = (max_chars - 1) // 2
    return f"{texto[:mitad]}…{texto[-mitad:]}"


class SplitView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        # Archivo y destino
        self.pdf_path = ""
        self.dest_path = ""
        self.dest_is_auto = False

        # Visor
        self.pdf_doc = None
        self.total_pages = 0
        self.current_page = 0
        self.rotations = {}
        self.excluded = set()
        self.current_ctk_image = None
        self._resize_timer = None
        self._last_container_size = None
        self._compact_toolbar = False

        # Configuración
        self.mode = "chapters"
        self.mode_labels = {modo: t(clave) for modo, clave in MODOS}
        self.mode_by_label = {etiqueta: modo for modo, etiqueta in self.mode_labels.items()}
        self.chapter_rows = []
        self.active_row = None
        self.plan = None
        self.plan_error = None
        self._update_job = None
        self.exported = False

        opciones = app.settings.get("options") or {}
        self.var_numbering = ctk.BooleanVar(value=opciones.get("numbering", False))
        self.var_bookmarks = ctk.BooleanVar(value=opciones.get("bookmarks", True))
        self.var_compress = ctk.BooleanVar(value=opciones.get("compress", False))
        self.var_single = ctk.BooleanVar(value=False)
        self.var_kw_name = ctk.BooleanVar(value=True)
        self.var_kw_before = ctk.BooleanVar(value=True)
        self.var_kw_case = ctk.BooleanVar(value=False)

        # Texto de cada página (se extrae una sola vez, para buscar y para el modo "Texto")
        self.page_texts = None
        self.search_query = ""
        self.search_pages = []
        self._search_job = None

        self._build()
        self.bind("<Configure>", self._on_configure)
        self.schedule_update()

    # ====================================================
    # Construcción de la interfaz
    # ====================================================
    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.stepper = StepIndicator(self, [t("step_choose"), t("step_configure"), t("step_export")])
        self.stepper.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        self.left = ctk.CTkFrame(self, fg_color="transparent", width=400)
        self.left.grid(row=1, column=0, sticky="ns", padx=(0, 16))
        self.left.grid_propagate(False)
        self.left.grid_columnconfigure(0, weight=1)
        self.left.grid_rowconfigure(2, weight=1)

        self._build_file_card()
        self._build_mode_selector()
        self._build_mode_card()
        self._build_options()

        self.execute_btn = button(self.left, t("split_button"), "cut", variant="success", size="lg", command=self.process)
        self.execute_btn.grid(row=4, column=0, sticky="ew")

        self._build_viewer()

    def _build_file_card(self):
        tarjeta = card(self.left)
        tarjeta.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        tarjeta.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tarjeta, text="", image=icon("file", 18, "accent_text"), width=36, height=36,
                     corner_radius=10, fg_color=C["accent_soft"]).grid(row=0, column=0, padx=(14, 10), pady=(14, 10))
        textos = ctk.CTkFrame(tarjeta, fg_color="transparent")
        textos.grid(row=0, column=1, sticky="ew", pady=(14, 10))
        self.file_title = label(textos, t("no_pdf_selected"), 14, "bold", anchor="w")
        self.file_title.pack(fill="x")
        self.file_sub = label(textos, t("file_card_hint"), 12, color="muted", anchor="w")
        self.file_sub.pack(fill="x")
        button(tarjeta, t("open"), "open_file", size="sm", command=self.select_pdf,
               tooltip=t("open_pdf_tip")).grid(row=0, column=2, padx=(8, 14), pady=(14, 10))

        ctk.CTkFrame(tarjeta, height=1, fg_color=C["border"]).grid(row=1, column=0, columnspan=3, sticky="ew", padx=14)

        ctk.CTkLabel(tarjeta, text="", image=icon("folder", 18, "muted"), width=36, height=36,
                     corner_radius=10, fg_color=C["surface_alt"]).grid(row=2, column=0, padx=(14, 10), pady=(10, 14))
        textos = ctk.CTkFrame(tarjeta, fg_color="transparent")
        textos.grid(row=2, column=1, sticky="ew", pady=(10, 14))
        label(textos, t("dest_folder"), 11, color="muted", anchor="w").pack(fill="x")
        self.dest_label = label(textos, t("dest_auto"), 13, anchor="w")
        self.dest_label.pack(fill="x")
        self.dest_tooltip = Tooltip(self.dest_label, "")
        button(tarjeta, t("change"), size="sm", command=self.select_dest).grid(row=2, column=2, padx=(8, 14), pady=(10, 14))

    def _build_mode_selector(self):
        fila = ctk.CTkFrame(self.left, fg_color="transparent")
        fila.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        fila.grid_columnconfigure(0, weight=1)
        self.mode_selector = segmented(fila, list(self.mode_labels.values()), command=lambda e: self.set_mode(self.mode_by_label[e]))
        self.mode_selector.set(self.mode_labels[self.mode])
        self.mode_selector.grid(row=0, column=0, sticky="ew")
        self.template_btn = button(fila, icon_name="more", variant="ghost", tooltip=t("templates_tip"),
                                   command=self.show_template_menu)
        self.template_btn.grid(row=0, column=1, padx=(6, 0))

    def _build_mode_card(self):
        self.mode_card = card(self.left)
        self.mode_card.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        self.mode_card.grid_rowconfigure(0, weight=1)
        self.mode_card.grid_columnconfigure(0, weight=1)

        self.mode_frames = {
            "chapters": self._build_chapters_frame(),
            "every": self._build_every_frame(),
            "ranges": self._build_ranges_frame(),
            "size": self._build_size_frame(),
            "keyword": self._build_keyword_frame(),
        }
        self._previews = {"every": self.every_preview, "ranges": self.ranges_preview, "keyword": self.keyword_preview}
        self.error_label = label(self.mode_card, "", 12, color="danger", anchor="w", justify="left", wraplength=340)
        self.error_label.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        self.error_label.grid_remove()
        self.mode_frames[self.mode].grid(row=0, column=0, sticky="nsew")

    def _mode_frame(self, description=None):
        """
        Panel de un modo. Los que tienen descripción son desplazables: en pantallas bajas la vista
        previa no entra. El de capítulos no, porque ya tiene su propia lista desplazable.
        """
        if description:
            marco = ctk.CTkScrollableFrame(self.mode_card, fg_color="transparent", scrollbar_button_color=C["border"])
            marco._descripcion = label(marco, description, 12, color="muted", anchor="w", justify="left", wraplength=320)
            marco._descripcion.pack(fill="x", padx=8, pady=(6, 8))
        else:
            marco = ctk.CTkFrame(self.mode_card, fg_color="transparent")
        return marco

    def _form_row(self, parent, texto, widget_factory):
        fila = ctk.CTkFrame(parent, fg_color="transparent")
        fila.pack(fill="x", padx=8, pady=4)
        label(fila, texto, 13, anchor="w").pack(side="left")
        widget = widget_factory(fila)
        widget.pack(side="right")
        return widget

    def _build_chapters_frame(self):
        marco = self._mode_frame()
        cabecera = ctk.CTkFrame(marco, fg_color="transparent")
        cabecera.pack(fill="x", padx=14, pady=(10, 4))
        label(cabecera, t("chapters"), 14, "bold").pack(side="left")
        self.chapter_count = label(cabecera, "", 12, color="muted")
        self.chapter_count.pack(side="left", padx=(6, 0))
        self.detect_btn = button(cabecera, t("detect_toc"), "search", variant="ghost", size="sm",
                                 tooltip=t("detect_toc_tip"), command=self.detect_chapters)
        self.detect_btn.pack(side="right")
        set_enabled(self.detect_btn, False)

        # Encabezados alineados con las columnas de cada fila (mismo orden de empaquetado)
        columnas = ctk.CTkFrame(marco, fg_color="transparent")
        columnas.pack(fill="x", padx=(8, 22), pady=(2, 0))
        label(columnas, "", width=24).pack(side="left", padx=(6, 6))
        label(columnas, "", width=28).pack(side="right", padx=(2, 4))
        label(columnas, t("col_end"), 11, color="muted", width=56).pack(side="right", padx=(6, 0))
        label(columnas, t("col_start"), 11, color="muted", width=56).pack(side="right", padx=(6, 0))
        label(columnas, t("col_name"), 11, color="muted", anchor="w").pack(side="left", fill="x", expand=True)

        self.rows_frame = ctk.CTkScrollableFrame(marco, fg_color="transparent", scrollbar_button_color=C["border"])
        self.rows_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.add_row_btn = button(self.rows_frame, t("add_chapter"), "add", variant="ghost", size="sm",
                                  command=lambda: self.add_chapter_row(focus=True))
        self.add_row_btn.pack(fill="x", padx=6, pady=(4, 2))
        self.add_chapter_row()
        return marco

    def _build_every_frame(self):
        marco = self._mode_frame(t("every_description"))
        self.every_n = self._form_row(marco, t("every_pages_label"), lambda p: entry(p, "10", width=90, justify="center"))
        self.every_name = self._form_row(marco, t("base_name"), lambda p: entry(p, t("default_part"), width=160))
        self.set_entry(self.every_n, "10")
        self.set_entry(self.every_name, t("default_part"))
        self.every_preview = label(marco, "", 12, color="muted", anchor="w", justify="left", wraplength=340)
        self.every_preview.pack(fill="x", padx=8, pady=(10, 4))
        for e in (self.every_n, self.every_name):
            e.bind("<KeyRelease>", lambda ev: self.schedule_update())
        return marco

    def _build_ranges_frame(self):
        marco = self._mode_frame(t("ranges_description"))
        self.ranges_text = entry(marco, "1-3, 5, 8-10")
        self.ranges_text.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkSwitch(marco, text=t("ranges_single"), variable=self.var_single,
                      font=font(13), text_color=C["text"], progress_color=C["accent"],
                      command=self.schedule_update).pack(anchor="w", padx=8, pady=6)
        self.ranges_name = self._form_row(marco, t("base_name"), lambda p: entry(p, t("default_excerpt"), width=160))
        self.set_entry(self.ranges_name, t("default_excerpt"))
        self.ranges_preview = label(marco, "", 12, color="muted", anchor="w", justify="left", wraplength=340)
        self.ranges_preview.pack(fill="x", padx=8, pady=(10, 4))
        for e in (self.ranges_text, self.ranges_name):
            e.bind("<KeyRelease>", lambda ev: self.schedule_update())
        return marco

    def _build_size_frame(self):
        marco = self._mode_frame(t("size_description"))
        self.size_mb = self._form_row(marco, t("size_max_label"), lambda p: entry(p, "10", width=90, justify="center"))
        self.set_entry(self.size_mb, "10")
        atajos = ctk.CTkFrame(marco, fg_color="transparent")
        atajos.pack(fill="x", padx=8, pady=(0, 4))
        for mb in (5, 10, 20, 25):
            button(atajos, f"{mb} MB", variant="secondary", size="sm", width=56,
                   command=lambda v=mb: (self.set_entry(self.size_mb, v), self.schedule_update())).pack(side="right", padx=(6, 0))
        self.size_name = self._form_row(marco, t("base_name"), lambda p: entry(p, t("default_part"), width=160))
        self.set_entry(self.size_name, t("default_part"))
        self.size_preview = label(marco, "", 12, color="muted", anchor="w", justify="left", wraplength=340)
        self.size_preview.pack(fill="x", padx=8, pady=(10, 4))
        for e in (self.size_mb, self.size_name):
            e.bind("<KeyRelease>", lambda ev: self.schedule_update())
        return marco

    def _build_options(self):
        fila = ctk.CTkFrame(self.left, fg_color="transparent")
        fila.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        checkbox(fila, t("opt_numbering"), self.var_numbering, tooltip=t("opt_numbering_tip"),
                 command=self.save_options).pack(side="left", padx=(2, 12))
        checkbox(fila, t("opt_bookmarks"), self.var_bookmarks, tooltip=t("opt_bookmarks_tip"),
                 command=self.save_options).pack(side="left", padx=(0, 12))
        checkbox(fila, t("opt_compress"), self.var_compress, tooltip=t("opt_compress_tip"),
                 command=self.save_options).pack(side="left")

    def _build_keyword_frame(self):
        marco = self._mode_frame(t("keyword_description"))
        self.keyword_text = entry(marco, t("keyword_placeholder"))
        self.keyword_text.pack(fill="x", padx=8, pady=(0, 6))
        interruptor = dict(font=font(13), text_color=C["text"], progress_color=C["accent"], command=self.schedule_update)
        ctk.CTkSwitch(marco, text=t("keyword_name_from_match"),
                      variable=self.var_kw_name, **interruptor).pack(anchor="w", padx=8, pady=4)
        ctk.CTkSwitch(marco, text=t("keyword_include_before"),
                      variable=self.var_kw_before, **interruptor).pack(anchor="w", padx=8, pady=4)
        ctk.CTkSwitch(marco, text=t("keyword_case"),
                      variable=self.var_kw_case, **interruptor).pack(anchor="w", padx=8, pady=4)
        self.keyword_name = self._form_row(marco, t("base_name"), lambda p: entry(p, t("default_part"), width=160))
        self.set_entry(self.keyword_name, t("default_part"))
        self.keyword_preview = label(marco, "", 12, color="muted", anchor="w", justify="left", wraplength=340)
        self.keyword_preview.pack(fill="x", padx=8, pady=(10, 4))
        for e in (self.keyword_text, self.keyword_name):
            e.bind("<KeyRelease>", lambda ev: self.schedule_update())
        return marco

    def _build_viewer(self):
        self.right = card(self)
        self.right.grid(row=1, column=1, sticky="nsew")

        # Barra superior: navegación, rotar y excluir
        barra = ctk.CTkFrame(self.right, fg_color="transparent")
        barra.pack(side="top", fill="x", padx=12, pady=(10, 8))
        self.prev_btn = button(barra, icon_name="prev", variant="ghost", tooltip=t("prev_page_tip"), command=self.prev_page)
        self.prev_btn.pack(side="left")
        self.page_entry = entry(barra, "-", width=52, justify="center")
        self.page_entry.pack(side="left", padx=(4, 4))
        self.page_entry.bind("<Return>", self._on_page_entry)
        self.page_total_label = label(barra, t("page_of", total="-"), 13, color="muted")
        self.page_total_label.pack(side="left", padx=(2, 4))
        self.next_btn = button(barra, icon_name="next", variant="ghost", tooltip=t("next_page_tip"), command=self.next_page)
        self.next_btn.pack(side="left")

        self.exclude_btn = button(barra, t("exclude"), "hide", variant="ghost", size="md", width=96,
                                  tooltip=t("exclude_tip"), command=self.toggle_exclude)
        self.exclude_btn.pack(side="right")
        self.rotate_btn = button(barra, t("rotate"), "rotate", variant="ghost", size="md", width=90,
                                 tooltip=t("rotate_tip"), command=self.rotate_page)
        self.rotate_btn.pack(side="right", padx=(0, 4))
        self.search_btn = button(barra, icon_name="find", variant="ghost", tooltip=t("search_tip"),
                                 command=lambda: self.toggle_search())
        self.search_btn.pack(side="right", padx=(0, 4))

        # Barra de búsqueda (oculta hasta que se abre con Ctrl+F o la lupa)
        self.search_bar = ctk.CTkFrame(self.right, fg_color=C["surface_alt"], corner_radius=10)
        self.search_entry = entry(self.search_bar, t("search_placeholder"), width=120)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(8, 6), pady=6)
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        self.search_entry.bind("<Escape>", lambda e: self.toggle_search(False))
        button(self.search_bar, icon_name="close", variant="ghost", size="sm", tooltip=t("search_close_tip"),
               command=lambda: self.toggle_search(False)).pack(side="right", padx=(0, 6))
        self.search_next_btn = button(self.search_bar, icon_name="down", variant="ghost", size="sm",
                                      tooltip=t("search_next_tip"), command=lambda: self.search_step(1))
        self.search_next_btn.pack(side="right")
        self.search_prev_btn = button(self.search_bar, icon_name="up", variant="ghost", size="sm",
                                      tooltip=t("search_prev_tip"), command=lambda: self.search_step(-1))
        self.search_prev_btn.pack(side="right")
        self.search_count = label(self.search_bar, "", 12, color="muted")
        self.search_count.pack(side="right", padx=(0, 8))
        self._search_visible = False

        # Parte inferior: miniaturas y botones de capítulo (se empaquetan antes que la imagen
        # para que nunca queden fuera de la ventana cuando hay poca altura)
        self.thumbs = ThumbnailStrip(self.right, on_select=self.go_to_page)
        self._show_thumbs = True

        self.page_actions = ctk.CTkFrame(self.right, fg_color="transparent")
        self.page_actions.grid_columnconfigure((0, 1), weight=1, uniform="pagina")
        self.use_start_btn = button(self.page_actions, t("use_as_start"), "upload", variant="secondary",
                                    tooltip=t("use_as_start_tip"), command=self.use_page_as_start)
        self.use_start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.use_end_btn = button(self.page_actions, t("use_as_end"), "download", variant="secondary",
                                  tooltip=t("use_as_end_tip"), command=self.use_page_as_end)
        self.use_end_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # Área de la página / zona para soltar archivos
        self.image_container = ctk.CTkFrame(self.right, fg_color=C["canvas"], corner_radius=10, border_width=2, border_color=C["canvas"])
        self._layout_viewer()
        self.preview_label = ctk.CTkLabel(self.image_container, text="")
        self.excluded_badge = ctk.CTkLabel(self.image_container, text=f"  {t('page_excluded')}  ", font=font(12, "bold"),
                                           fg_color=C["danger"], text_color=C["on_accent"], corner_radius=6, height=26)
        self._build_empty_state()

        self.image_container.bind("<Configure>", self._on_container_resize)
        for widget in (self.image_container, self.preview_label):
            widget.bind("<MouseWheel>", self._on_mouse_wheel)
            widget.bind("<Button-1>", self._on_container_click)
            widget.bind("<Enter>", lambda e: self.set_drop_highlight(self.pdf_doc is None))
            widget.bind("<Leave>", lambda e: self.set_drop_highlight(False))

        self._set_viewer_enabled(False)

    def _build_empty_state(self):
        self.empty_state = ctk.CTkFrame(self.image_container, fg_color="transparent")
        self.empty_state.place(relx=0.5, rely=0.5, anchor="center")
        mascota = theme.brand_image("icon", 120)
        if mascota:
            ctk.CTkLabel(self.empty_state, text="", image=mascota).pack(pady=(0, 10))
        else:
            # Un CTkButton respeta el ancho exacto, así el círculo no se deforma
            ctk.CTkButton(self.empty_state, text="", image=icon("upload", 30, "accent_text"), width=72, height=72,
                          corner_radius=36, fg_color=C["accent_soft"], hover_color=C["accent_soft"],
                          command=self.select_pdf).pack(pady=(0, 14))
        titulo = t("empty_drop_title") if self.app.dnd_enabled else t("empty_open_title")
        label(self.empty_state, titulo, 17, "bold").pack()
        label(self.empty_state, t("empty_subtitle"), 13, color="muted").pack(pady=(2, 14))
        button(self.empty_state, t("choose_file"), "open_file", variant="primary", command=self.select_pdf).pack()
        self.recents_frame = ctk.CTkFrame(self.empty_state, fg_color="transparent")
        self.recents_frame.pack(fill="x", pady=(18, 0))
        self.refresh_recents()

    def refresh_recents(self):
        for hijo in self.recents_frame.winfo_children():
            hijo.destroy()
        recientes = self.app.settings.recent_files()[:4]
        if not recientes:
            return
        label(self.recents_frame, t("recent").upper(), 11, "bold", color="faint", anchor="w").pack(fill="x", padx=4, pady=(0, 4))
        for ruta in recientes:
            btn = button(self.recents_frame, acortar_texto(os.path.basename(ruta), 40), "history", variant="ghost", size="sm",
                         anchor="w", tooltip=ruta, command=lambda r=ruta: self.open_pdf(r))
            btn.pack(fill="x")
        self.app.enable_drop(self.recents_frame)

    # ====================================================
    # Responsividad
    # ====================================================
    def _on_configure(self, event):
        if event.widget is not self:
            return
        escala = ctk.ScalingTracker.get_window_scaling(self)
        ancho, alto = event.width / escala, event.height / escala
        nuevo_ancho = int(max(330, min(440, ancho * 0.42)))
        if self.left.cget("width") != nuevo_ancho:
            self.left.configure(width=nuevo_ancho)
            wrap = nuevo_ancho - 40
            self.error_label.configure(wraplength=wrap)
            # Los paneles desplazables pierden ancho por la barra de desplazamiento
            for lbl in (self.every_preview, self.ranges_preview, self.size_preview, self.keyword_preview):
                lbl.configure(wraplength=wrap - 30)
            for marco in self.mode_frames.values():
                if hasattr(marco, "_descripcion"):
                    marco._descripcion.configure(wraplength=wrap - 30)
            self._refresh_path_labels()

        # Con poco ancho, Rotar/Excluir muestran solo el ícono (el tooltip explica qué hacen)
        compacto = ancho - nuevo_ancho < 520
        if compacto != self._compact_toolbar:
            self._compact_toolbar = compacto
            self.rotate_btn.configure(text="" if compacto else t("rotate"), width=34 if compacto else 90)
            self._update_exclude_button()

        # En pantallas bajas se ocultan elementos secundarios para priorizar la página
        if alto < 600:
            self.stepper.grid_remove()
        else:
            self.stepper.grid()
        mostrar_miniaturas = alto >= 560
        if mostrar_miniaturas != self._show_thumbs:
            self._show_thumbs = mostrar_miniaturas
            self._layout_viewer()

    def _layout_viewer(self):
        """Reempaqueta la parte inferior del visor respetando el orden (lo de abajo va primero)."""
        for widget in (self.thumbs, self.page_actions, self.image_container):
            widget.pack_forget()
        if self._show_thumbs:
            self.thumbs.pack(side="bottom", fill="x", padx=12, pady=(6, 10))
        if self.mode == "chapters":
            self.page_actions.pack(side="bottom", fill="x", padx=12, pady=(8, 0 if self._show_thumbs else 12))
        bottom_pad = 0 if (self._show_thumbs or self.mode == "chapters") else 12
        self.image_container.pack(fill="both", expand=True, padx=12, pady=(0, bottom_pad))

    def _on_container_resize(self, event):
        size = (event.width, event.height)
        if size == self._last_container_size:
            return
        self._last_container_size = size
        if self._resize_timer:
            self.after_cancel(self._resize_timer)
        self._resize_timer = self.after(120, self.update_preview_image)

    def refresh_theme(self):
        self.thumbs.refresh_theme()

    # ====================================================
    # Archivo / destino
    # ====================================================
    def select_pdf(self):
        if self.app.busy:
            return
        ruta = filedialog.askopenfilename(parent=self.app, filetypes=[(t("filetype_pdf"), "*.pdf")])
        if ruta:
            self.open_pdf(ruta)

    def open_pdf(self, ruta):
        try:
            doc = self.app.open_fitz(ruta)  # Pide la contraseña si el PDF está protegido
            if doc is None:
                return False
            if doc.page_count == 0:
                doc.close()
                raise ValueError(t("err_no_pages"))
        except Exception as e:
            Dialog.alert(self.app, t("err_open_pdf"), str(e))
            return False

        if self.pdf_doc:
            self.pdf_doc.close()
        self.pdf_doc = doc
        self.pdf_path = os.path.normpath(ruta)
        self.total_pages = doc.page_count
        self.current_page = 0
        self.rotations = {}
        self.excluded = set()
        self.exported = False
        self.page_texts = None
        self.search_pages = []
        self.app.settings.add_recent(self.pdf_path)
        self.refresh_recents()

        try:
            tamano = core.formatear_tamano(os.path.getsize(self.pdf_path))
        except OSError:
            tamano = "?"
        self._refresh_path_labels()
        self.file_sub.configure(text=f"{t('pages_count', n=self.total_pages)} · {tamano}")

        # Carpeta destino por defecto: una subcarpeta junto al PDF original
        if not self.dest_path or self.dest_is_auto:
            base = os.path.splitext(os.path.basename(self.pdf_path))[0]
            self._set_dest(os.path.join(os.path.dirname(self.pdf_path), f"{base}_{t('suffix_split')}"), auto=True)

        self.empty_state.place_forget()
        self.preview_label.place(relx=0.5, rely=0.5, anchor="center")
        self.set_drop_highlight(False)
        self._set_viewer_enabled(True)
        self.thumbs.set_document(doc)
        self.go_to_page(0)
        if self._search_visible and self.search_entry.get().strip():
            self._run_search()
        self.schedule_update()

        if doc.get_toc() and self.mode == "chapters" and not self._chapters_have_data():
            self.app.toast(t("toc_hint"), "info")
        return True

    def select_dest(self):
        inicial = self.dest_path if self.dest_path and os.path.isdir(self.dest_path) else None
        carpeta = filedialog.askdirectory(parent=self.app, initialdir=inicial)
        if carpeta:
            self._set_dest(carpeta, auto=False)

    def _set_dest(self, ruta, auto):
        self.dest_path = os.path.normpath(ruta)
        self.dest_is_auto = auto
        self.dest_tooltip.text = self.dest_path
        self._refresh_path_labels()

    def _refresh_path_labels(self):
        """Acorta nombre y ruta según el ancho disponible en el panel."""
        caracteres = max(16, int((self.left.cget("width") - 190) / 8.2))
        if self.pdf_path:
            self.file_title.configure(text=acortar_texto(os.path.basename(self.pdf_path), caracteres - 4))
        if self.dest_path:
            self.dest_label.configure(text=acortar_texto(self.dest_path, caracteres))

    # ====================================================
    # Visor
    # ====================================================
    def _set_viewer_enabled(self, enabled):
        for btn in (self.rotate_btn, self.exclude_btn, self.use_start_btn, self.use_end_btn, self.detect_btn):
            set_enabled(btn, enabled)
        if not enabled:
            set_enabled(self.prev_btn, False)
            set_enabled(self.next_btn, False)

    def set_drop_highlight(self, active):
        self.image_container.configure(border_color=C["accent"] if active else C["canvas"])
        self.image_container.configure(cursor="hand2" if self.pdf_doc is None else "")

    def _on_container_click(self, event):
        if self.pdf_doc is None:
            self.select_pdf()

    def go_to_page(self, index):
        if not self.pdf_doc:
            return
        self.current_page = max(0, min(index, self.total_pages - 1))
        self.update_preview_image()
        self.thumbs.set_current(self.current_page)

    def update_preview_image(self):
        self._resize_timer = None
        if not self.pdf_doc:
            return

        # Indicadores y botones
        self.set_entry(self.page_entry, self.current_page + 1)
        self.page_total_label.configure(text=t("page_of", total=self.total_pages))
        set_enabled(self.prev_btn, self.current_page > 0)
        set_enabled(self.next_btn, self.current_page < self.total_pages - 1)
        excluida = self.current_page in self.excluded
        self._update_exclude_button()
        if excluida:
            self.excluded_badge.place(relx=0.5, y=12, anchor="n")
            self.excluded_badge.lift()
        else:
            self.excluded_badge.place_forget()

        # Espacio disponible en píxeles físicos
        margen = 24
        max_ancho = self.image_container.winfo_width() - margen
        max_alto = self.image_container.winfo_height() - margen
        if max_ancho < 50 or max_alto < 50:
            return

        try:
            pagina = self.pdf_doc.load_page(self.current_page)
            rot = self.rotations.get(self.current_page, 0)
            ancho, alto = (pagina.rect.height, pagina.rect.width) if rot % 180 else (pagina.rect.width, pagina.rect.height)
            # Renderizar directamente al tamaño necesario (nítido también en pantallas HiDPI)
            zoom = min(max_ancho / ancho, max_alto / alto, 5.0)
            matriz = fitz.Matrix(zoom, zoom).prerotate(rot)
            pix = pagina.get_pixmap(matrix=matriz, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            if self.search_query and self.current_page in self.search_pages:
                img = self._highlight_matches(img, pagina, matriz)
            if excluida:
                img = Image.blend(img, Image.new("RGB", img.size, (60, 60, 60)), 0.55)
        except Exception as e:
            self.preview_label.configure(image="", text=t("err_render_page", error=e), text_color=C["muted"])
            return

        # CTkImage recibe tamaño lógico y lo multiplica por el escalado del widget
        escala = ctk.ScalingTracker.get_widget_scaling(self.preview_label)
        tamano_logico = (max(1, round(pix.width / escala)), max(1, round(pix.height / escala)))
        self.current_ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=tamano_logico)
        self.preview_label.configure(image=self.current_ctk_image, text="")

    def _update_exclude_button(self):
        excluida = self.pdf_doc is not None and self.current_page in self.excluded
        texto = "" if self._compact_toolbar else (t("include") if excluida else t("exclude"))
        self.exclude_btn.configure(text=texto, width=34 if self._compact_toolbar else 96,
                                   image=icon("view" if excluida else "hide", 16, "muted"))

    def prev_page(self):
        if self.pdf_doc and self.current_page > 0:
            self.go_to_page(self.current_page - 1)

    def next_page(self):
        if self.pdf_doc and self.current_page < self.total_pages - 1:
            self.go_to_page(self.current_page + 1)

    def _on_page_entry(self, event):
        try:
            self.go_to_page(int(self.page_entry.get()) - 1)
        except ValueError:
            self.set_entry(self.page_entry, self.current_page + 1)
        self.app.focus_set()

    def _on_mouse_wheel(self, event):
        if event.delta < 0:
            self.next_page()
        elif event.delta > 0:
            self.prev_page()

    def rotate_page(self):
        if not self.pdf_doc:
            return
        rot = (self.rotations.get(self.current_page, 0) + 90) % 360
        if rot:
            self.rotations[self.current_page] = rot
        else:
            self.rotations.pop(self.current_page, None)
        self.thumbs.rotations = self.rotations
        self.thumbs.invalidate(self.current_page)
        self.update_preview_image()

    def toggle_exclude(self):
        if not self.pdf_doc:
            return
        if self.current_page in self.excluded:
            self.excluded.discard(self.current_page)
        else:
            self.excluded.add(self.current_page)
        self.thumbs.set_marks(excluded=self.excluded)
        self.update_preview_image()
        self.schedule_update()

    # ====================================================
    # Búsqueda de texto
    # ====================================================
    def get_page_texts(self):
        """Texto de cada página del PDF abierto (se extrae una vez y se reutiliza)."""
        if self.page_texts is None and self.pdf_doc is not None:
            self.app.configure(cursor="watch")
            self.app.update_idletasks()
            try:
                self.page_texts = [self.pdf_doc.load_page(i).get_text() for i in range(self.total_pages)]
            except Exception:
                self.page_texts = [""] * self.total_pages
            finally:
                self.app.configure(cursor="")
        return self.page_texts

    def toggle_search(self, show=None):
        show = not self._search_visible if show is None else show
        if show == self._search_visible:
            if show:
                self.search_entry.focus_set()
            return
        self._search_visible = show
        if show:
            self.search_bar.pack(side="top", fill="x", padx=12, pady=(0, 8), after=self.search_btn.master)
            self.search_entry.focus_set()
            self.search_entry.select_range(0, "end")
            if self.search_entry.get().strip():
                self._run_search()
        else:
            self.search_bar.pack_forget()
            self.search_query, self.search_pages = "", []
            self.thumbs.set_marks(matches=set())
            self.update_preview_image()
            self.app.focus_set()

    def _on_search_key(self, event):
        if event.keysym == "Return":
            self.search_step(-1 if event.state & 0x1 else 1)  # Shift+Enter = anterior
            return
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(250, self._run_search)

    def _run_search(self):
        self._search_job = None
        consulta = self.search_entry.get().strip()
        self.search_query = consulta
        if not consulta or not self.pdf_doc:
            self.search_pages = []
            self.search_count.configure(text="")
        else:
            self.search_pages = core.paginas_con_texto(self.get_page_texts(), consulta)
            n = len(self.search_pages)
            self.search_count.configure(text=t("pages_count", n=n) if n else t("search_no_results"),
                                        text_color=C["muted"] if n else C["danger"])
        self.thumbs.set_marks(matches=set(self.search_pages))
        for btn in (self.search_prev_btn, self.search_next_btn):
            set_enabled(btn, bool(self.search_pages))
        # Ir al primer resultado desde la página actual
        if self.search_pages and self.current_page not in self.search_pages:
            self.search_step(1)
        else:
            self.update_preview_image()

    def search_step(self, direccion):
        if not self.search_pages:
            return
        if direccion > 0:
            destino = next((p for p in self.search_pages if p > self.current_page), self.search_pages[0])
        else:
            destino = next((p for p in reversed(self.search_pages) if p < self.current_page), self.search_pages[-1])
        self.go_to_page(destino)
        posicion = self.search_pages.index(destino) + 1
        self.search_count.configure(text=t("search_position", i=posicion, n=len(self.search_pages)), text_color=C["muted"])

    def _highlight_matches(self, img, pagina, matriz):
        """Pinta en amarillo las apariciones del texto buscado sobre la imagen de la página."""
        try:
            rects = pagina.search_for(self.search_query)
        except Exception:
            return img
        if not rects:
            return img
        origen = (pagina.rect * matriz).irect
        capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dibujo = ImageDraw.Draw(capa)
        for r in rects:
            rr = r * matriz
            caja = (rr.x0 - origen.x0 - 2, rr.y0 - origen.y0 - 2, rr.x1 - origen.x0 + 2, rr.y1 - origen.y0 + 2)
            dibujo.rectangle(caja, fill=(250, 204, 21, 110), outline=(234, 179, 8, 255), width=2)
        return Image.alpha_composite(img.convert("RGBA"), capa).convert("RGB")

    def handle_key(self, event):
        """Atajos de teclado del visor. Devuelve True si se usó la tecla."""
        if event.keysym == "Escape" and self._search_visible:
            self.toggle_search(False)
            return True
        teclas = {"Left": self.prev_page, "Right": self.next_page, "r": self.rotate_page, "x": self.toggle_exclude}
        accion = teclas.get(event.keysym if event.keysym in ("Left", "Right") else event.keysym.lower())
        if accion:
            accion()
            return True
        return False

    # ====================================================
    # Arrastrar y soltar
    # ====================================================
    def handle_drop(self, rutas):
        pdfs = [r for r in rutas if r.lower().endswith(".pdf")]
        plantillas = [r for r in rutas if r.lower().endswith(".json")]
        if pdfs:
            self.open_pdf(pdfs[0])
        elif plantillas:
            self.load_template(plantillas[0])
        else:
            Dialog.alert(self.app, t("invalid_file_title"), t("invalid_file_message"))

    # ====================================================
    # Modos
    # ====================================================
    def set_mode(self, modo):
        if modo == self.mode:
            return
        self.mode_frames[self.mode].grid_remove()
        self.mode = modo
        self.mode_selector.set(self.mode_labels[modo])
        self.mode_frames[modo].grid(row=0, column=0, sticky="nsew")
        self._layout_viewer()
        self.schedule_update()

    # ====================================================
    # Capítulos
    # ====================================================
    def add_chapter_row(self, name="", start="", end="", focus=False):
        fila = ctk.CTkFrame(self.rows_frame, fg_color="transparent", corner_radius=8)
        fila.pack(fill="x", padx=2, pady=2, before=self.add_row_btn)
        datos = {"frame": fila}

        punto = ctk.CTkLabel(fila, text="", width=24, height=24, corner_radius=12, font=font(11, "bold"),
                             fg_color=C["surface_alt"], text_color=C["muted"])
        punto.pack(side="left", padx=(6, 6), pady=4)
        button(fila, icon_name="delete", variant="danger_ghost", size="sm", tooltip=t("delete_chapter"),
               command=lambda: self.remove_chapter_row(datos)).pack(side="right", padx=(2, 4))
        fin = entry(fila, t("col_end"), width=56, justify="center")
        fin.pack(side="right", padx=(6, 0))
        inicio = entry(fila, t("col_start"), width=56, justify="center")
        inicio.pack(side="right", padx=(6, 0))
        nombre = entry(fila, t("chapter_name_placeholder"), width=100)
        nombre.pack(side="left", fill="x", expand=True)

        datos.update({"dot": punto, "name": nombre, "start": inicio, "end": fin})
        self.chapter_rows.append(datos)

        for campo, valor in ((nombre, name), (inicio, start), (fin, end)):
            if valor != "":
                self.set_entry(campo, valor)
            campo.bind("<FocusIn>", lambda e: self.set_active_row(datos))
            campo.bind("<KeyRelease>", lambda e: self.schedule_update())
        inicio.bind("<FocusOut>", lambda e: (self.autofill_previous_end(datos), self.schedule_update()))

        self.set_active_row(datos)
        self.app.enable_drop(fila)
        if focus:
            nombre.focus_set()
            self.after(50, lambda: self.rows_frame._parent_canvas.yview_moveto(1.0))
        self.schedule_update()
        return datos

    def remove_chapter_row(self, datos):
        datos["frame"].destroy()
        if datos in self.chapter_rows:
            self.chapter_rows.remove(datos)
        if self.active_row is datos:
            self.active_row = None
            if self.chapter_rows:
                self.set_active_row(self.chapter_rows[-1])
        self.schedule_update()

    def clear_chapter_rows(self):
        for fila in list(self.chapter_rows):
            fila["frame"].destroy()
        self.chapter_rows.clear()
        self.active_row = None

    def set_active_row(self, datos):
        if self.active_row is datos:
            return
        if self.active_row is not None and self.active_row["frame"].winfo_exists():
            self.active_row["frame"].configure(fg_color="transparent")
        self.active_row = datos
        datos["frame"].configure(fg_color=C["accent_soft"])

    def _chapters_have_data(self):
        return any(f[c].get().strip() for f in self.chapter_rows for c in ("name", "start", "end"))

    @staticmethod
    def set_entry(widget, valor):
        widget.delete(0, "end")
        widget.insert(0, str(valor))

    @staticmethod
    def entry_int(widget):
        try:
            return int(widget.get().strip())
        except ValueError:
            return None

    def autofill_previous_end(self, datos):
        """Si el capítulo anterior no tiene fin, se completa con (inicio de este capítulo - 1)."""
        if datos not in self.chapter_rows:
            return
        idx = self.chapter_rows.index(datos)
        if idx == 0:
            return
        anterior = self.chapter_rows[idx - 1]
        inicio = self.entry_int(datos["start"])
        inicio_anterior = self.entry_int(anterior["start"])
        if inicio is None or inicio_anterior is None or anterior["end"].get().strip():
            return
        if inicio - 1 >= inicio_anterior:
            self.set_entry(anterior["end"], inicio - 1)

    def ensure_active_row(self):
        if self.active_row is None or self.active_row not in self.chapter_rows:
            if self.chapter_rows:
                self.set_active_row(self.chapter_rows[-1])
            else:
                self.add_chapter_row()
        return self.active_row

    def use_page_as_start(self):
        if not self.pdf_doc:
            return
        fila = self.ensure_active_row()
        self.set_entry(fila["start"], self.current_page + 1)
        self.autofill_previous_end(fila)
        self.schedule_update()

    def use_page_as_end(self):
        if not self.pdf_doc:
            return
        fila = self.ensure_active_row()
        self.set_entry(fila["end"], self.current_page + 1)

        # Pasar al siguiente capítulo (creándolo si hace falta) para seguir marcando
        idx = self.chapter_rows.index(fila)
        if idx + 1 < len(self.chapter_rows):
            self.set_active_row(self.chapter_rows[idx + 1])
        else:
            self.add_chapter_row()
            self.after(50, lambda: self.rows_frame._parent_canvas.yview_moveto(1.0))
        self.schedule_update()

    def detect_chapters(self):
        if not self.pdf_doc:
            return
        capitulos = core.capitulos_desde_indice(self.pdf_doc.get_toc(), self.total_pages)
        if not capitulos:
            Dialog.alert(self.app, t("no_toc_title"), t("no_toc_message"), "info")
            return
        if self._chapters_have_data() and not Dialog.confirm(
                self.app, t("replace_chapters_title"), t("replace_chapters_message", n=len(capitulos)), t("replace")):
            return
        self.load_chapters(capitulos)
        self.app.toast(t("toc_detected", n=len(capitulos)), "success")

    def load_chapters(self, capitulos):
        self.clear_chapter_rows()
        for nombre, inicio, fin in capitulos:
            self.add_chapter_row(nombre, inicio, fin)
        if not self.chapter_rows:
            self.add_chapter_row()
        self.set_active_row(self.chapter_rows[0])
        self.after(50, lambda: self.rows_frame._parent_canvas.yview_moveto(0.0))

    def _validate_chapter_rows(self):
        """
        Valida cada fila y marca en rojo los campos con problemas.
        Devuelve (capítulos válidos [(fila, nombre, inicio, fin)], primer mensaje de error o None).
        """
        validos, mensaje, usados = [], None, {}
        for fila in self.chapter_rows:
            nombre = fila["name"].get().strip()
            inicio_txt, fin_txt = fila["start"].get().strip(), fila["end"].get().strip()
            errores = set()
            if not (nombre or inicio_txt or fin_txt):
                self._mark_row(fila, errores)
                continue

            inicio, fin = self.entry_int(fila["start"]), self.entry_int(fila["end"])
            if not nombre:
                errores.add("name")
                mensaje = mensaje or t("err_chapter_no_name")
            if inicio is None:
                errores.add("start")
                mensaje = mensaje or (t("err_missing_start") if not inicio_txt else t("err_pages_int"))
            if fin is None:
                errores.add("end")
                mensaje = mensaje or (t("err_missing_end") if not fin_txt else t("err_pages_int"))
            if inicio is not None and fin is not None:
                if inicio < 1 or (self.total_pages and inicio > self.total_pages):
                    errores.add("start")
                if fin < 1 or (self.total_pages and fin > self.total_pages):
                    errores.add("end")
                if inicio > fin:
                    errores.update(("start", "end"))
                if {"start", "end"} & errores:
                    limite = " " + t("pdf_has_pages", n=self.total_pages) if self.total_pages else ""
                    mensaje = mensaje or t("err_row_range", name=nombre or t("unnamed"), start=inicio, end=fin) + limite
            if nombre:
                archivo = core.nombre_archivo_seguro(nombre).lower()
                if archivo in usados:
                    errores.add("name")
                    mensaje = mensaje or t("err_duplicate_names", a=nombre, b=usados[archivo])
                usados.setdefault(archivo, nombre)

            self._mark_row(fila, errores)
            if not errores:
                validos.append((fila, nombre, inicio, fin))
        return validos, mensaje

    @staticmethod
    def _mark_row(fila, errores):
        for campo in ("name", "start", "end"):
            fila[campo].configure(border_color=C["danger"] if campo in errores else C["border"])

    # ====================================================
    # Plan (se recalcula en vivo)
    # ====================================================
    def get_spec(self):
        if self.mode == "chapters":
            capitulos = []
            for fila in self.chapter_rows:
                nombre = fila["name"].get().strip()
                inicio, fin = fila["start"].get().strip(), fila["end"].get().strip()
                if nombre or inicio or fin:
                    capitulos.append([nombre, self.entry_int(fila["start"]) or inicio, self.entry_int(fila["end"]) or fin])
            return {"mode": "chapters", "chapters": capitulos}
        if self.mode == "every":
            return {"mode": "every", "n": self.every_n.get().strip(), "name": self.every_name.get().strip() or t("default_part")}
        if self.mode == "ranges":
            return {"mode": "ranges", "text": self.ranges_text.get().strip(), "single_file": bool(self.var_single.get()),
                    "name": self.ranges_name.get().strip() or t("default_excerpt")}
        if self.mode == "keyword":
            return {"mode": "keyword", "text": self.keyword_text.get().strip(), "case_sensitive": bool(self.var_kw_case.get()),
                    "name": self.keyword_name.get().strip() or t("default_part"), "name_from_match": bool(self.var_kw_name.get()),
                    "include_before": bool(self.var_kw_before.get())}
        return {"mode": "size", "max_mb": self.size_mb.get().strip(), "name": self.size_name.get().strip() or t("default_part")}

    def apply_spec(self, spec):
        modo = spec.get("mode")
        if modo not in core.MODOS:
            raise PlanError(t("err_template_mode"))
        if modo == "chapters":
            self.load_chapters([(str(n), s, e) for n, s, e in spec.get("chapters", [])])
        elif modo == "every":
            self.set_entry(self.every_n, spec.get("n", 10))
            self.set_entry(self.every_name, spec.get("name") or t("default_part"))
        elif modo == "ranges":
            self.set_entry(self.ranges_text, spec.get("text", ""))
            self.var_single.set(bool(spec.get("single_file")))
            self.set_entry(self.ranges_name, spec.get("name") or t("default_excerpt"))
        elif modo == "keyword":
            self.set_entry(self.keyword_text, spec.get("text", ""))
            self.set_entry(self.keyword_name, spec.get("name") or t("default_part"))
            self.var_kw_case.set(bool(spec.get("case_sensitive")))
            self.var_kw_name.set(bool(spec.get("name_from_match", True)))
            self.var_kw_before.set(bool(spec.get("include_before", True)))
        else:
            self.set_entry(self.size_mb, spec.get("max_mb", 10))
            self.set_entry(self.size_name, spec.get("name") or t("default_part"))
        self.set_mode(modo)
        self.schedule_update()

    def schedule_update(self):
        if self._update_job is not None:
            self.after_cancel(self._update_job)
        self._update_job = self.after(150, self.update_plan)

    def update_plan(self):
        self._update_job = None
        self.plan, self.plan_error = None, None
        colores_pagina = {}

        plan_colores = []
        if self.mode == "chapters":
            validos, mensaje = self._validate_chapter_rows()
            # Número y color de cada fila según su posición (igual que en las miniaturas)
            filas_validas = {id(f) for f, *_r in validos}
            posicion = {}
            for n, fila in enumerate(self.chapter_rows):
                color = CHAPTER_COLORS[n % len(CHAPTER_COLORS)]
                posicion[id(fila)] = color
                if id(fila) in filas_validas:
                    fila["dot"].configure(text=str(n + 1), fg_color=color, text_color="#FFFFFF")
                else:
                    fila["dot"].configure(text=str(n + 1), fg_color=C["surface_alt"], text_color=C["muted"])
            plan_colores = [posicion[id(f)] for f, *_r in validos]
            cantidad = len(validos)
            self.chapter_count.configure(text="· " + t("chapters_ready", n=cantidad) if cantidad else "")
            if mensaje:
                self.plan_error = mensaje
            elif validos and self.pdf_doc:
                self.plan = [(n, list(range(s - 1, e))) for _, n, s, e in validos]

        elif self.pdf_doc:
            spec = self.get_spec()
            if self.mode == "size":
                self._update_size_preview(spec)
            else:
                try:
                    if self.mode == "keyword" and not spec["text"]:
                        # Todavía no se escribió nada: no se muestra un error de entrada
                        self._previews["keyword"].configure(text="")
                    else:
                        textos = self.get_page_texts() if self.mode == "keyword" else None
                        self.plan = core.build_plan(spec, self.total_pages, textos_pagina=textos)
                except PlanError as e:
                    self.plan_error = str(e)
        else:
            for lbl in (self.every_preview, self.ranges_preview, self.size_preview, self.keyword_preview):
                lbl.configure(text=t("open_pdf_to_preview"))

        if self.plan:
            for i, (_, paginas) in enumerate(self.plan):
                color = plan_colores[i] if i < len(plan_colores) else CHAPTER_COLORS[i % len(CHAPTER_COLORS)]
                for p in paginas:
                    colores_pagina.setdefault(p, color)
            self._update_mode_preview()
        elif self.mode in self._previews and self.plan_error:
            self._previews[self.mode].configure(text="")

        self.thumbs.set_marks(colors=colores_pagina)

        if self.plan_error:
            self.error_label.configure(text=self.plan_error)
            self.error_label.grid()
        else:
            self.error_label.grid_remove()

        valido = bool(self.plan) or (self.mode == "size" and self.pdf_doc is not None and not self.plan_error)
        if self.plan:
            n = len(self.plan)
            self.execute_btn.configure(text=t("split_into", n=n))
        else:
            self.execute_btn.configure(text=t("split_button"))

        hechos = set()
        if self.pdf_doc:
            hechos.add(0)
        if valido:
            hechos.add(1)
        if self.exported and valido:
            hechos.add(2)
        activo = next((i for i in range(3) if i not in hechos), 2)
        self.stepper.set_state(hechos, activo)

    def _describe_plan(self, max_items=4):
        partes = []
        for nombre, paginas in self.plan[:max_items]:
            visibles = [p for p in paginas if p not in self.excluded]
            if not visibles:
                rango = t("plan_empty")
            elif len(paginas) == 1:
                rango = t("plan_page", page=paginas[0] + 1)
            elif paginas == list(range(paginas[0], paginas[-1] + 1)):
                rango = t("plan_pages", start=paginas[0] + 1, end=paginas[-1] + 1)
            else:
                rango = t("plan_pages_count", n=len(visibles))
            partes.append(f"• {nombre} ({rango})")
        if len(self.plan) > max_items:
            partes.append("• " + t("plan_more", n=len(self.plan) - max_items))
        return "\n".join(partes)

    def _update_mode_preview(self):
        if self.mode not in self._previews:
            return
        n = len(self.plan)
        texto = t("plan_will_generate", n=n) + "\n" + self._describe_plan()
        if self.excluded:
            texto += "\n\n" + t("plan_excluded", n=len(self.excluded))
        self._previews[self.mode].configure(text=texto)

    def _update_size_preview(self, spec):
        try:
            max_mb = float(str(spec["max_mb"]).replace(",", "."))
            if max_mb <= 0:
                raise ValueError
        except ValueError:
            self.plan_error = t("err_size_number")
            self.size_preview.configure(text="")
            return
        try:
            tamano = os.path.getsize(self.pdf_path)
        except OSError:
            tamano = 0
        estimado = max(1, math.ceil(tamano / (max_mb * 1024 * 1024)))
        self.size_preview.configure(
            text=t("size_preview", size=core.formatear_tamano(tamano), n=estimado))

    # ====================================================
    # Opciones y plantillas
    # ====================================================
    def get_options(self):
        return {"numbering": bool(self.var_numbering.get()), "bookmarks": bool(self.var_bookmarks.get()),
                "compress": bool(self.var_compress.get())}

    def save_options(self):
        self.app.settings.set("options", self.get_options())

    def show_template_menu(self):
        menu = tkinter.Menu(self, tearoff=0, bg=resolve(C["surface"]), fg=resolve(C["text"]),
                            activebackground=resolve(C["accent"]), activeforeground="#FFFFFF", bd=0,
                            font=(None, 10))
        menu.add_command(label="  " + t("template_save"), command=self.save_template)
        menu.add_command(label="  " + t("template_load"), command=lambda: self.load_template())
        x = self.template_btn.winfo_rootx()
        y = self.template_btn.winfo_rooty() + self.template_btn.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def save_template(self):
        sufijo = t("template_file_suffix")
        nombre = f"{os.path.splitext(os.path.basename(self.pdf_path))[0]}_{sufijo}.json" if self.pdf_path else f"{sufijo}.json"
        ruta = filedialog.asksaveasfilename(parent=self.app, defaultextension=".json", initialfile=nombre,
                                            filetypes=[(t("filetype_template"), "*.json")])
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump({"app": APP_NAME, "version": 1, "spec": self.get_spec(),
                           "options": self.get_options()}, f, ensure_ascii=False, indent=2)
        except OSError as e:
            Dialog.alert(self.app, t("err_save"), str(e))
            return
        self.app.toast(t("template_saved"), "success")

    def load_template(self, ruta=None):
        ruta = ruta or filedialog.askopenfilename(parent=self.app, filetypes=[(t("filetype_template"), "*.json")])
        if not ruta:
            return
        try:
            with open(ruta, encoding="utf-8") as f:
                datos = json.load(f)
            spec = datos.get("spec", datos)
            self.apply_spec(spec)
            for clave, var in (("numbering", self.var_numbering), ("bookmarks", self.var_bookmarks), ("compress", self.var_compress)):
                if clave in datos.get("options", {}):
                    var.set(bool(datos["options"][clave]))
        except (OSError, ValueError, TypeError, AttributeError, PlanError) as e:
            Dialog.alert(self.app, t("template_invalid_title"), t("template_invalid_message", error=e))
            return
        self.app.toast(t("template_loaded", spec=core.describir_spec(spec)), "success")

    # ====================================================
    # Procesamiento
    # ====================================================
    def process(self):
        if self.app.busy:
            return
        if not self.pdf_doc:
            Dialog.alert(self.app, t("missing_pdf_title"), t("split_missing_pdf"), "info")
            return
        if self._update_job is not None:
            self.after_cancel(self._update_job)
        self.update_plan()
        if self.plan_error or (self.mode != "size" and not self.plan):
            Dialog.alert(self.app, t("check_config"),
                         self.plan_error or {"chapters": t("err_add_chapter"), "keyword": t("err_keyword_empty")}.get(
                             self.mode, t("err_invalid_config")))
            return

        spec = self.get_spec()
        opciones = self.get_options()
        destino = self.dest_path

        if self.plan:
            existentes = [n for n in core.nombres_de_salida(self.plan, opciones["numbering"])
                          if os.path.exists(os.path.join(destino, n))]
            if existentes and not Dialog.confirm(
                    self.app, t("overwrite_title"), t("overwrite_message", n=len(existentes)), t("overwrite"), danger=True):
                return

        self.save_options()
        ruta, rotaciones, excluidas = self.pdf_path, dict(self.rotations), set(self.excluded)
        password = self.app.password_for(ruta)
        # En modo "Texto" se reutiliza el texto ya extraído con PyMuPDF (coincide con la vista previa)
        textos = list(self.get_page_texts()) if self.mode == "keyword" else None

        def tarea(log, cancel):
            return core.split_pdf(ruta, spec, destino, opciones, log, cancel, rotaciones, excluidas,
                                  password=password, textos_pagina=textos)

        def al_terminar(resultado):
            generados, errores, cancelado = resultado
            if cancelado:
                self.app.toast(t("split_cancelled", n=generados), "info")
            elif not errores:
                self.exported = True
                self.update_plan()
                self.app.toast(t("split_done", n=generados), "success",
                               action=(t("open_folder"), lambda: self.app.open_folder(destino)))
            else:
                titulo = t("done_with_errors") if generados else t("split_failed")
                Dialog.alert(self.app, titulo, t("generated_with_problems", n=generados),
                             detail="\n".join(errores))

        self.app.run_task(t("split_progress"), tarea, al_terminar)

    def close_document(self):
        if self.pdf_doc:
            self.pdf_doc.close()
            self.pdf_doc = None
