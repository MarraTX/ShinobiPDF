"""Ventana principal: barra lateral, vistas, tema, arrastrar y soltar y tareas en segundo plano."""
import os
import queue
import subprocess
import sys
import threading
import tkinter
import traceback
import webbrowser

import customtkinter as ctk
import fitz  # PyMuPDF

from . import APP_NAME, APP_VERSION, i18n, logs, onboarding, theme, updates
from .i18n import t
from .settings import Settings
from .settings_dialog import SettingsDialog
from .split_view import SplitView
from .theme import C, font, icon
from .tools_views import BatchView, ImagesView, MergeView
from .widgets import Dialog, PasswordDialog, ProgressDialog, Toast, Tooltip, label

# Arrastrar y soltar es opcional: si tkinterdnd2 no está instalado la app funciona igual
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_DISPONIBLE = True
except ImportError:
    DND_DISPONIBLE = False

_AppBase = (ctk.CTk, TkinterDnD.DnDWrapper) if DND_DISPONIBLE else (ctk.CTk,)

# (vista, clave de traducción, ícono)
NAV = [
    ("split", "nav_split", "cut"),
    ("merge", "nav_merge", "merge"),
    ("images", "nav_images", "image"),
    ("batch", "nav_batch", "layers"),
]


class App(*_AppBase):
    # Tamaño preferido y mínimo de la ventana (en unidades lógicas, antes del escalado DPI)
    PREFERRED_SIZE = (1280, 800)
    MIN_SIZE = (860, 540)
    COMPACT_BELOW = 1060  # Ancho por debajo del cual la barra lateral muestra solo íconos

    def __init__(self, files=None):
        super().__init__()
        theme.apply_window_icon(self)
        self.settings = Settings()
        i18n.set_language(i18n.detect_language(self.settings.get("language")))
        logs.setup()
        sys.excepthook = lambda tipo, valor, tb: logs.log.error("Error no controlado", exc_info=(tipo, valor, tb))
        self.passwords = {}  # Contraseñas de PDFs protegidos abiertos en esta sesión
        ctk.set_appearance_mode(self.settings.get("theme"))
        ctk.set_default_color_theme("blue")
        theme.init_fonts(self)

        self.title(APP_NAME)
        self.configure(fg_color=C["bg"])
        self.busy = False
        self.current_view = None
        self.views = {}
        self._toast = None
        self._toast_job = None
        self._compact = None

        self.dnd_enabled = False
        if DND_DISPONIBLE:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.dnd_enabled = True
            except Exception:
                pass

        self.fit_to_screen()
        self._build()
        self.show_view("split")
        if self.dnd_enabled:
            self.enable_drop(self)

        self.bind("<KeyPress>", self._on_key)
        self.bind("<Control-o>", lambda e: self.views["split"].select_pdf() if self.current_view == "split" else None)
        self.bind("<Control-f>", lambda e: self.views["split"].toggle_search(True) if self.current_view == "split" else None)
        self.bind("<Configure>", self._on_configure)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Archivos recibidos al abrir la app (desde el Explorador o la línea de comandos)
        if files:
            self.after(400, lambda: self.open_files(files))
        self.after(700, self._startup_checks)

    # ----------------------------------------------------
    # Inicio: bienvenida, novedades y actualizaciones
    # ----------------------------------------------------
    def _startup_checks(self):
        primera_vez = not self.settings.get("onboarding_done")
        version_anterior = self.settings.get("last_version")
        self.settings.set("last_version", APP_VERSION)
        if primera_vez:
            onboarding.WelcomeTour(self, on_close=lambda: self.settings.set("onboarding_done", True))
        elif version_anterior and version_anterior != APP_VERSION:
            onboarding.show_whats_new(self)
        self.after(4000, lambda: updates.check_in_background(self))

    def check_updates_now(self):
        self.toast(t("update_checking"), "info", duration_ms=3000)
        updates.check_in_background(self, manual=True)

    def on_update_result(self, resultado, manual):
        if isinstance(resultado, Exception):
            logs.log.warning("No se pudo buscar actualizaciones: %s", resultado)
            if manual:
                Dialog.alert(self, t("update_error_title"), t("update_error_message"), "info")
        elif resultado is None:
            if manual:
                self.toast(t("update_none", version=APP_VERSION), "success")
        else:
            logs.log.info("Versión nueva disponible: %s", resultado["version"])
            self.toast(t("update_available", version=resultado["version"]), "info",
                       action=(t("update_download"), lambda: webbrowser.open(resultado["url"])), duration_ms=20000)

    # ----------------------------------------------------
    # Errores no previstos
    # ----------------------------------------------------
    def report_callback_exception(self, tipo, valor, tb):
        """Tkinter llama a este método cuando falla algo dentro de un evento de la interfaz."""
        logs.log.error("Error en la interfaz", exc_info=(tipo, valor, tb))
        self._show_error_with_report(valor)

    def _show_error_with_report(self, error):
        dialogo = Dialog(self, t("err_unexpected"), t("err_unexpected_message", error=error), "error",
                         buttons=((t("report_problem"), True, "primary"), (t("close"), False, "secondary")))
        self.wait_window(dialogo)
        if dialogo.result:
            logs.open_report(f"Error: {error}")

    def open_files(self, rutas):
        rutas = [os.path.abspath(r) for r in rutas if os.path.exists(r)]
        pdfs = [r for r in rutas if r.lower().endswith(".pdf")]
        plantillas = [r for r in rutas if r.lower().endswith(".json")]
        if len(pdfs) > 1:
            # Varios PDFs a la vez: se preparan para dividirlos en lote
            self.show_view("batch")
            self.views["batch"].handle_drop(pdfs)
        elif pdfs or plantillas:
            self.show_view("split")
            self.views["split"].handle_drop(pdfs or plantillas)

    # ----------------------------------------------------
    # PDFs protegidos con contraseña
    # ----------------------------------------------------
    def password_for(self, ruta):
        return self.passwords.get(os.path.normcase(os.path.abspath(ruta)))

    def passwords_for(self, rutas):
        return {r: self.password_for(r) for r in rutas if self.password_for(r)}

    def open_fitz(self, ruta):
        """
        Abre un PDF con PyMuPDF pidiendo la contraseña si hace falta.
        Devuelve el documento, o None si el usuario canceló. Lanza la excepción si el archivo no es válido.
        """
        doc = fitz.open(ruta)
        if not doc.needs_pass:
            return doc
        clave = os.path.normcase(os.path.abspath(ruta))
        if clave in self.passwords and doc.authenticate(self.passwords[clave]):
            return doc
        error = None
        while True:
            password = PasswordDialog.ask(self, os.path.basename(ruta), error)
            if password is None:
                doc.close()
                return None
            if doc.authenticate(password):
                self.passwords[clave] = password
                return doc
            error = t("pw_wrong")

    # ----------------------------------------------------
    # Ventana
    # ----------------------------------------------------
    def window_scaling(self):
        return ctk.ScalingTracker.get_window_scaling(self)

    def fit_to_screen(self):
        """Ajusta el tamaño de la ventana a la pantalla (notebooks, escalado DPI, etc.)."""
        scaling = self.window_scaling()
        screen_w = self.winfo_screenwidth() / scaling
        screen_h = self.winfo_screenheight() / scaling

        # Se deja margen para la barra de tareas y el borde de la ventana
        width = int(min(self.PREFERRED_SIZE[0], screen_w * 0.92))
        height = int(min(self.PREFERRED_SIZE[1], screen_h * 0.85))
        min_w = min(self.MIN_SIZE[0], width)
        min_h = min(self.MIN_SIZE[1], height)

        # La posición se expresa en píxeles físicos
        x = max(0, int((self.winfo_screenwidth() - width * scaling) / 2))
        y = max(0, int((self.winfo_screenheight() - height * scaling) / 3))

        self.minsize(min_w, min_h)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # En pantallas muy pequeñas se maximiza directamente
        if screen_w < self.MIN_SIZE[0] + 60 or screen_h < self.MIN_SIZE[1] + 80:
            self.after(0, lambda: self.state("zoomed"))

    def _build(self):
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Barra lateral
        self.sidebar = ctk.CTkFrame(self, fg_color=C["sidebar"], corner_radius=0, width=220)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.pack_propagate(False)
        ctk.CTkFrame(self, width=1, fg_color=C["border"], corner_radius=0).grid(row=0, column=1, sticky="ns")

        # Marca: logo horizontal con la barra expandida, solo el ícono cuando está compacta
        marca = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        marca.pack(fill="x", padx=12, pady=(16, 18))
        logo = theme.brand_image("logo", 52)
        icono = theme.brand_image("icon", 44)
        self.brand_full = ctk.CTkFrame(marca, fg_color="transparent")
        ctk.CTkLabel(self.brand_full, text="" if logo else APP_NAME, image=logo, font=font(16, "bold"), anchor="w").pack(anchor="w")
        label(self.brand_full, f"v{APP_VERSION}", 11, color="muted", anchor="w").pack(anchor="w", padx=(6, 0))
        self.brand_compact = ctk.CTkLabel(marca, text="" if icono else "S", image=icono, font=font(14, "bold"))
        self.brand_full.pack(fill="x")

        self.nav_buttons = {}
        for clave, clave_texto, nombre_icono in NAV:
            texto = t(clave_texto)
            btn = ctk.CTkButton(self.sidebar, text=texto, anchor="w", height=40, corner_radius=10, font=font(14),
                                fg_color="transparent", hover_color=C["hover"], text_color=C["text"],
                                image=icon(nombre_icono, 18, "muted"), compound="left",
                                command=lambda c=clave: self.show_view(c))
            btn.pack(fill="x", padx=10, pady=2)
            btn._icon_name = nombre_icono
            btn._text = texto
            Tooltip(btn, texto)
            self.nav_buttons[clave] = btn

        self.theme_btn = ctk.CTkButton(self.sidebar, text="", anchor="w", height=40, corner_radius=10, font=font(13),
                                       fg_color="transparent", hover_color=C["hover"], text_color=C["muted"],
                                       compound="left", command=self.toggle_theme)
        self.theme_btn.pack(side="bottom", fill="x", padx=10, pady=(0, 14))
        self.settings_btn = ctk.CTkButton(self.sidebar, text=t("settings"), anchor="w", height=40, corner_radius=10, font=font(13),
                                          fg_color="transparent", hover_color=C["hover"], text_color=C["muted"],
                                          image=icon("settings", 18, "muted"), compound="left",
                                          command=lambda: SettingsDialog(self))
        self.settings_btn.pack(side="bottom", fill="x", padx=10, pady=(0, 2))
        self.settings_btn._text = t("settings")
        Tooltip(self.settings_btn, t("settings"))
        self._update_theme_button()

        # Contenido
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=2, sticky="nsew", padx=22, pady=20)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.views["split"] = SplitView(self.content, self)
        self.views["merge"] = MergeView(self.content, self)
        self.views["images"] = ImagesView(self.content, self)
        self.views["batch"] = BatchView(self.content, self)

    def show_view(self, clave):
        if clave == self.current_view:
            return
        if self.current_view:
            self.views[self.current_view].grid_remove()
        self.current_view = clave
        vista = self.views[clave]
        vista.grid(row=0, column=0, sticky="nsew")
        if hasattr(vista, "on_show"):
            vista.on_show()
        for c, btn in self.nav_buttons.items():
            activo = c == clave
            btn.configure(fg_color=C["accent_soft"] if activo else "transparent",
                          text_color=C["accent_text"] if activo else C["text"],
                          image=icon(btn._icon_name, 18, "accent_text" if activo else "muted"))

    def _on_configure(self, event):
        if event.widget is not self:
            return
        compacto = event.width / self.window_scaling() < self.COMPACT_BELOW
        if compacto == self._compact:
            return
        self._compact = compacto
        self.sidebar.configure(width=68 if compacto else 220)
        if compacto:
            self.brand_full.pack_forget()
            self.brand_compact.pack()
        else:
            self.brand_compact.pack_forget()
            self.brand_full.pack(fill="x")
        for btn in (*self.nav_buttons.values(), self.settings_btn):
            btn.configure(text="" if compacto else btn._text, anchor="center" if compacto else "w")
        self._update_theme_button()

    # ----------------------------------------------------
    # Tema
    # ----------------------------------------------------
    def toggle_theme(self):
        nuevo = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        ctk.set_appearance_mode(nuevo)
        self.settings.set("theme", nuevo)
        self._update_theme_button()
        for vista in self.views.values():
            if hasattr(vista, "refresh_theme"):
                vista.refresh_theme()

    def _update_theme_button(self):
        oscuro = ctk.get_appearance_mode() == "Dark"
        texto = t("theme_light") if oscuro else t("theme_dark")
        self.theme_btn.configure(image=icon("sun" if oscuro else "moon", 18, "muted"),
                                 text="" if self._compact else texto, anchor="center" if self._compact else "w")

    # ----------------------------------------------------
    # Avisos, carpetas y tareas
    # ----------------------------------------------------
    def toast(self, message, kind="success", action=None, duration_ms=7000):
        self._hide_toast()
        self._toast = Toast(self, message, kind, action, on_close=lambda t: self._hide_toast())
        self._toast.place(relx=1.0, rely=0.0, x=-24, y=20, anchor="ne")
        self._toast.lift()
        self._toast_job = self.after(duration_ms, self._hide_toast)

    def _hide_toast(self):
        if self._toast_job:
            self.after_cancel(self._toast_job)
            self._toast_job = None
        if self._toast is not None:
            toast, self._toast = self._toast, None
            if toast.winfo_exists():
                toast.destroy()

    def open_folder(self, ruta):
        try:
            if os.name == "nt":
                os.startfile(ruta)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", ruta])
        except Exception as e:
            Dialog.alert(self, t("err_open_folder"), str(e))

    def run_task(self, title, func, on_done, cancellable=True):
        """
        Ejecuta func(log, cancel_event) en un hilo con un diálogo de progreso.
        Los mensajes pasan por una cola: Tkinter solo debe tocarse desde el hilo principal.
        """
        if self.busy:
            return
        self.busy = True
        dialogo = ProgressDialog(self, title, cancellable)
        mensajes = queue.Queue()
        resultado = {}

        def log(mensaje, es_error=False, progreso=None):
            mensajes.put((mensaje, es_error, progreso))

        def trabajador():
            try:
                resultado["value"] = func(log, dialogo.cancel_event)
            except Exception as e:
                logs.log.error("Error en la tarea «%s»\n%s", title, traceback.format_exc())
                resultado["error"] = e

        hilo = threading.Thread(target=trabajador, daemon=True)
        hilo.start()

        def revisar():
            while not mensajes.empty():
                mensaje, es_error, progreso = mensajes.get_nowait()
                if not dialogo.cancel_event.is_set():
                    dialogo.update_status(mensaje, es_error, progreso)
                elif progreso is not None:
                    dialogo.update_status(t("cancelling"), False, progreso)
            if hilo.is_alive():
                self.after(50, revisar)
            else:
                self.after(250, terminar)

        def terminar():
            self.busy = False
            dialogo.close()
            if "error" in resultado:
                self._show_error_with_report(resultado["error"])
            else:
                on_done(resultado["value"])

        revisar()

    # ----------------------------------------------------
    # Arrastrar y soltar
    # ----------------------------------------------------
    def enable_drop(self, widget):
        """Registra un widget y sus hijos: en Windows cada widget recibe sus propios drops."""
        if not self.dnd_enabled:
            return
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<DropEnter>>", self._on_drop_enter)
            widget.dnd_bind("<<DropLeave>>", self._on_drop_leave)
            widget.dnd_bind("<<Drop>>", self._on_drop)
        except (AttributeError, tkinter.TclError):
            pass
        for hijo in widget.winfo_children():
            if not isinstance(hijo, tkinter.Toplevel):
                self.enable_drop(hijo)

    def _drop_highlight(self, activo):
        vista = self.views.get(self.current_view)
        if hasattr(vista, "set_drop_highlight"):
            vista.set_drop_highlight(activo)

    def _on_drop_enter(self, event):
        self._drop_highlight(True)
        return event.action

    def _on_drop_leave(self, event):
        self._drop_highlight(False)
        return event.action

    def _on_drop(self, event):
        self._drop_highlight(False)
        if not self.busy:
            rutas = list(self.tk.splitlist(event.data))
            self.views[self.current_view].handle_drop(rutas)
        return event.action

    # ----------------------------------------------------
    # Teclado y cierre
    # ----------------------------------------------------
    def _on_key(self, event):
        # No usar atajos mientras se escribe en un campo de texto
        try:
            foco = self.focus_get()
        except (KeyError, tkinter.TclError):
            foco = None
        if isinstance(foco, (tkinter.Entry, tkinter.Text)) or event.state & 0x4:  # 0x4 = Ctrl
            return
        if self.current_view == "split" and not self.busy:
            self.views["split"].handle_key(event)

    def on_close(self):
        if self.busy and not Dialog.confirm(self, t("busy_title"), t("busy_message"), t("quit"), danger=True):
            return
        self.views["split"].close_document()
        self.destroy()

    def restart(self):
        """Reabre la app (por ejemplo, para aplicar un cambio de idioma)."""
        if getattr(sys, "frozen", False):
            comando = [sys.executable]
        else:
            comando = [sys.executable, os.path.abspath(sys.argv[0])]
        archivo = self.views["split"].pdf_path
        if archivo:
            comando.append(archivo)
        subprocess.Popen(comando, close_fds=True)
        self.views["split"].close_document()
        self.destroy()
