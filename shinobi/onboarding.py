"""Tour de bienvenida (primera vez que se abre la app) y novedades (después de actualizar)."""
import tkinter

import customtkinter as ctk

from . import APP_VERSION, i18n, theme
from .i18n import t
from .theme import C
from .widgets import Dialog, button, center_on_parent, label, make_modal

# (ícono o None para el ninja, clave del título, clave del texto)
PASOS = [
    (None, "tour_1_title", "tour_1_text"),
    ("upload", "tour_2_title", "tour_2_text"),
    ("cut", "tour_3_title", "tour_3_text"),
    ("find", "tour_4_title", "tour_4_text"),
    ("layers", "tour_5_title", "tour_5_text"),
]


class WelcomeTour(ctk.CTkToplevel):
    ANCHO = 460

    def __init__(self, app, on_close=None):
        super().__init__(app)
        self.app = app
        self.on_close = on_close
        self.paso = 0
        self.title(t("tour_window_title"))
        self.resizable(False, False)
        self.configure(fg_color=C["surface"])

        self.cuerpo = ctk.CTkFrame(self, fg_color="transparent", width=self.ANCHO, height=300)
        self.cuerpo.pack(padx=30, pady=(26, 6))
        self.cuerpo.pack_propagate(False)
        self.imagen = ctk.CTkLabel(self.cuerpo, text="", width=124, height=124)
        self.imagen.pack(pady=(4, 16))
        self.titulo = label(self.cuerpo, "", 19, "bold", justify="center", wraplength=self.ANCHO)
        self.titulo.pack()
        self.texto = label(self.cuerpo, "", 13, color="muted", justify="center", wraplength=self.ANCHO - 20)
        self.texto.pack(pady=(8, 0))

        self.puntos = ctk.CTkFrame(self, fg_color="transparent")
        self.puntos.pack(pady=(4, 14))
        self.indicadores = [ctk.CTkFrame(self.puntos, width=8, height=8, corner_radius=4) for _ in PASOS]
        for punto in self.indicadores:
            punto.pack(side="left", padx=3)

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=24, pady=(0, 20))
        self.saltar = button(pie, t("tour_skip"), variant="ghost", command=self.close)
        self.saltar.pack(side="left")
        self.siguiente = button(pie, t("tour_next"), variant="primary", width=120, command=self.next)
        self.siguiente.pack(side="right")
        self.anterior = button(pie, t("tour_back"), variant="secondary", width=100, command=self.back)

        self.bind("<Right>", lambda e: self.next())
        self.bind("<Left>", lambda e: self.back())
        self.bind("<Return>", lambda e: self.next())
        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._show()
        center_on_parent(app, self)
        make_modal(app, self)

    def _show(self):
        nombre_icono, clave_titulo, clave_texto = PASOS[self.paso]
        # El círculo de fondo viene dibujado en la imagen: así no se deforma con ningún escalado
        imagen = theme.brand_image("icon", 120) if nombre_icono is None else theme.icon_badge(nombre_icono)
        self.imagen.configure(image=imagen)
        self.titulo.configure(text=t(clave_titulo))
        self.texto.configure(text=t(clave_texto))
        for i, punto in enumerate(self.indicadores):
            punto.configure(fg_color=C["accent"] if i == self.paso else C["border"], width=20 if i == self.paso else 8)
        ultimo = self.paso == len(PASOS) - 1
        self.siguiente.configure(text=t("tour_start") if ultimo else t("tour_next"))
        if self.paso > 0:
            # Con side="right" lo empaquetado después queda a la izquierda
            self.anterior.pack(side="right", padx=(0, 8), after=self.siguiente)
        else:
            self.anterior.pack_forget()
        self.saltar.configure(text="" if ultimo else t("tour_skip"), state="disabled" if ultimo else "normal")

    def next(self):
        if self.paso < len(PASOS) - 1:
            self.paso += 1
            self._show()
        else:
            self.close()

    def back(self):
        if self.paso > 0:
            self.paso -= 1
            self._show()

    def close(self):
        try:
            self.grab_release()
        except tkinter.TclError:
            pass
        self.destroy()
        if self.on_close:
            self.on_close()


def news_key(version=APP_VERSION):
    """Clave de traducción con las novedades de una versión (ej. 'news_1_1')."""
    return "news_" + version.replace(".", "_")


def show_whats_new(app, version=APP_VERSION):
    """Muestra las novedades de la versión si hay texto para ella. Devuelve True si se mostró."""
    clave = news_key(version)
    if not i18n.has(clave):
        return False
    Dialog.alert(app, t("whats_new_title", version=version), t(clave), "success")
    return True
