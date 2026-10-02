"""Ventanas de ajustes y «Acerca de»."""
import tkinter
import webbrowser

import customtkinter as ctk

from . import APP_NAME, APP_VERSION, REPO_URL, i18n, integration, logs, theme
from .i18n import t
from .theme import C, font
from .widgets import Dialog, button, center_on_parent, label, make_modal, segmented

# Librerías incluidas en la app y sus licencias (la AGPL exige mostrar los avisos de terceros)
# Código secreto de PDF Ninja (el minijuego de shinobipdf.com): desbloquea una katana exclusiva
NINJA_CODE = "DIVIDIYVENCERAS"

CREDITOS = [
    ("CustomTkinter", "MIT"),
    ("PyMuPDF / MuPDF", "AGPL-3.0"),
    ("pypdf", "BSD-3-Clause"),
    ("Pillow", "MIT-CMU"),
    ("tkinterdnd2 / tkdnd", "MIT"),
    ("cryptography", "Apache-2.0 / BSD"),
    ("Python", "PSF License"),
]


class _Ventana(ctk.CTkToplevel):
    """Base de las ventanas modales de esta sección."""

    def __init__(self, app, titulo):
        super().__init__(app)
        self.app = app
        self.title(titulo)
        self.resizable(False, False)
        self.configure(fg_color=C["surface"])
        self.bind("<Escape>", lambda e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _mostrar(self):
        center_on_parent(self.app, self)
        make_modal(self.app, self)

    @staticmethod
    def _section(parent, titulo):
        label(parent, titulo.upper(), 11, "bold", color="faint", anchor="w").pack(fill="x", pady=(0, 8))

    def _close(self):
        try:
            self.grab_release()
        except tkinter.TclError:
            pass
        self.destroy()


class SettingsDialog(_Ventana):
    def __init__(self, app):
        super().__init__(app, t("settings"))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=26, pady=(22, 8))

        # Idioma
        self._section(body, t("settings_language"))
        self.nombres_idioma = {nombre: codigo for codigo, nombre in i18n.LANGUAGES.items()}
        self.language = segmented(body, list(self.nombres_idioma), command=self._change_language)
        self.language.set(i18n.LANGUAGES[i18n.current_language()])
        self.language.pack(anchor="w")
        self.restart_row = ctk.CTkFrame(body, fg_color="transparent")
        label(self.restart_row, t("settings_language_restart"), 12, color="muted").pack(side="left")
        button(self.restart_row, t("settings_restart_now"), variant="primary", size="sm",
               command=self._restart).pack(side="left", padx=(10, 0))
        ctk.CTkFrame(body, height=16, fg_color="transparent").pack()

        # Actualizaciones
        self._section(body, t("settings_updates"))
        fila = ctk.CTkFrame(body, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 16))
        self.var_updates = ctk.BooleanVar(value=bool(app.settings.get("check_updates")))
        ctk.CTkSwitch(fila, text=t("settings_updates_auto"), variable=self.var_updates, font=font(13),
                      text_color=C["text"], progress_color=C["accent"],
                      command=lambda: app.settings.set("check_updates", bool(self.var_updates.get()))).pack(side="left")
        button(fila, t("settings_updates_now"), "sync", variant="secondary", size="sm",
               command=self._check_updates).pack(side="right")

        # Integración con el Explorador
        self._section(body, t("settings_windows"))
        self.var_menu = ctk.BooleanVar(value=integration.is_installed())
        interruptor = ctk.CTkSwitch(body, text=t("settings_context_menu"), variable=self.var_menu, font=font(13),
                                    text_color=C["text"], progress_color=C["accent"], command=self._toggle_menu)
        interruptor.pack(anchor="w")
        if not integration.available():
            interruptor.configure(state="disabled")
        label(body, t("settings_context_menu_hint"), 12, color="muted", anchor="w").pack(fill="x", padx=(48, 0), pady=(2, 16))

        # Archivos recientes
        self._section(body, t("settings_recent"))
        fila = ctk.CTkFrame(body, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 8))
        self.recent_label = label(fila, t("settings_recent_count", n=len(app.settings.recent_files())), 13, color="muted")
        self.recent_label.pack(side="left")
        button(fila, t("settings_recent_clear"), "delete", variant="secondary", size="sm",
               command=self._clear_recent).pack(side="right")

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=26, pady=(8, 20))
        button(pie, t("about"), "info", variant="ghost", size="sm",
               command=lambda: (self._close(), AboutDialog(app))).pack(side="left")
        button(pie, t("report_problem"), "error", variant="ghost", size="sm",
               command=lambda: logs.open_report()).pack(side="left", padx=(4, 0))
        button(pie, t("close"), variant="primary", width=110, command=self._close).pack(side="right")
        self._mostrar()

    def _change_language(self, nombre):
        codigo = self.nombres_idioma[nombre]
        self.app.settings.set("language", codigo)
        if integration.is_installed():
            # Volver a escribir el texto del menú contextual en el idioma nuevo
            anterior = i18n.current_language()
            i18n.set_language(codigo)
            try:
                integration.install()
            except OSError:
                pass
            i18n.set_language(anterior)
        if codigo != i18n.current_language():
            self.restart_row.pack(anchor="w", pady=(8, 0), after=self.language)
        else:
            self.restart_row.pack_forget()

    def _restart(self):
        self._close()
        self.app.restart()

    def _check_updates(self):
        self._close()
        self.app.check_updates_now()

    def _toggle_menu(self):
        try:
            if self.var_menu.get():
                integration.install()
                self.app.toast(t("settings_context_menu_done"), "success")
            else:
                integration.uninstall()
        except OSError as e:
            self.var_menu.set(integration.is_installed())
            Dialog.alert(self, t("settings_context_menu_error"), str(e))

    def _clear_recent(self):
        self.app.settings.set("recent", [])
        self.app.views["split"].refresh_recents()
        self.recent_label.configure(text=t("settings_recent_count", n=0))


class AboutDialog(_Ventana):
    def __init__(self, app):
        super().__init__(app, t("about"))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=(24, 8))

        logo = theme.brand_image("logo", 56)
        if logo:
            ctk.CTkLabel(body, text="", image=logo).pack(anchor="w")
        label(body, t("settings_version", name=APP_NAME, version=APP_VERSION), 12, color="muted", anchor="w").pack(fill="x", pady=(2, 10))
        label(body, t("about_tagline"), 13, anchor="w", justify="left", wraplength=380).pack(fill="x")
        label(body, t("about_license"), 12, color="muted", anchor="w", justify="left", wraplength=380).pack(fill="x", pady=(8, 12))
        # Easter egg: el código de la katana exclusiva del minijuego de la web
        label(body, t("about_ninja_code", code=NINJA_CODE), 12, color="muted", anchor="w", justify="left", wraplength=380).pack(fill="x", pady=(0, 12))

        enlaces = ctk.CTkFrame(body, fg_color="transparent")
        enlaces.pack(fill="x", pady=(0, 16))
        button(enlaces, t("settings_source_code"), variant="secondary", size="sm",
               command=lambda: webbrowser.open(REPO_URL)).pack(side="left")
        button(enlaces, t("about_view_license"), variant="ghost", size="sm",
               command=lambda: webbrowser.open(f"{REPO_URL}/blob/main/LICENSE")).pack(side="left", padx=(6, 0))
        button(enlaces, t("about_logs"), variant="ghost", size="sm",
               command=logs.open_log_folder).pack(side="left", padx=(2, 0))

        self._section(body, t("about_credits"))
        tabla = ctk.CTkFrame(body, fg_color=C["surface_alt"], corner_radius=10)
        tabla.pack(fill="x")
        for i, (nombre, licencia) in enumerate(CREDITOS):
            label(tabla, nombre, 12, anchor="w").grid(row=i, column=0, sticky="w", padx=(14, 20), pady=(8 if i == 0 else 2, 8 if i == len(CREDITOS) - 1 else 2))
            label(tabla, licencia, 12, color="muted", anchor="e").grid(row=i, column=1, sticky="e", padx=(0, 14))
        tabla.grid_columnconfigure(1, weight=1)

        button(self, t("close"), variant="primary", width=110, command=self._close).pack(anchor="e", padx=28, pady=(14, 20))
        self._mostrar()
