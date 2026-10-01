"""Sistema de diseño: colores (claro, oscuro), tipografías e íconos."""
import os
import tkinter.font

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

# Cada color es una tupla (modo claro, modo oscuro) que CustomTkinter resuelve solo
# Paleta basada en el logo de Shinobi.pdf: azul del documento (#333AFB) y azul marino del texto (#070E26)
C = {
    "bg": ("#F4F5FA", "#0B0E1A"),
    "sidebar": ("#FFFFFF", "#10142A"),
    "surface": ("#FFFFFF", "#141932"),
    "surface_alt": ("#F1F2F8", "#1B2140"),
    "input": ("#F8F9FC", "#0F1328"),
    "border": ("#E3E5EF", "#262D4D"),
    "hover": ("#ECEEF7", "#222A4A"),
    "text": ("#070E26", "#E9EBF5"),
    "muted": ("#5F6683", "#8E95B2"),
    "faint": ("#A0A5BC", "#565E80"),
    "accent": ("#333AFB", "#4F55FF"),
    "accent_hover": ("#2329DE", "#3D44F5"),
    "accent_soft": ("#ECEDFF", "#1F2558"),
    "accent_text": ("#2329DE", "#AEB2FF"),
    "success": ("#059669", "#10B981"),
    "success_hover": ("#047857", "#059669"),
    "danger": ("#DC2626", "#EF4444"),
    "danger_hover": ("#B91C1C", "#DC2626"),
    "danger_soft": ("#FEF2F2", "#3A1D22"),
    "warning": ("#D97706", "#F59E0B"),
    "canvas": ("#E6E8F2", "#080B16"),
    "on_accent": ("#FFFFFF", "#FFFFFF"),
}

# Colores para distinguir capítulos en las miniaturas
CHAPTER_COLORS = ["#4F55FF", "#10B981", "#F59E0B", "#EC4899", "#06B6D4", "#8B5CF6", "#84CC16", "#F97316"]

_FONT_FAMILY = "Segoe UI"
_DISPLAY_FAMILY = "Segoe UI"


def init_fonts(root):
    """Elige la mejor tipografía disponible (necesita una ventana ya creada)."""
    global _FONT_FAMILY, _DISPLAY_FAMILY
    familias = set(tkinter.font.families(root))
    for candidata in ("Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", "Arial"):
        if candidata in familias:
            _FONT_FAMILY = candidata
            break
    for candidata in ("Segoe UI Variable Display", _FONT_FAMILY):
        if candidata in familias:
            _DISPLAY_FAMILY = candidata
            break


def font_family():
    return _FONT_FAMILY


def font(size=13, weight="normal", display=False, slant="roman"):
    return ctk.CTkFont(family=_DISPLAY_FAMILY if display else _FONT_FAMILY, size=size, weight=weight, slant=slant)


def resolve(color):
    """Devuelve el color concreto según el modo actual (para widgets de Tk puro como Canvas)."""
    if isinstance(color, (tuple, list)):
        return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
    return color


# ----------------------------------------------------
# Íconos: glifos de la fuente de íconos de Windows renderizados como imágenes
# ----------------------------------------------------
ICON_FONT_PATHS = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "SegoeIcons.ttf"),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segmdl2.ttf"),
]

GLYPHS = {
    "add": 0xE710, "close": 0xE711, "check": 0xE73E, "search": 0xE721,
    "folder": 0xE8B7, "folder_open": 0xE838, "file": 0xE8A5, "page": 0xE7C3,
    "cut": 0xE8C6, "save": 0xE74E, "rotate": 0xE7AD, "sun": 0xE706, "moon": 0xE708,
    "image": 0xE8B9, "info": 0xE946, "warning": 0xE7BA, "history": 0xE81C,
    "delete": 0xE74D, "prev": 0xE76B, "next": 0xE76C, "up": 0xE70E, "down": 0xE70D,
    "merge": 0xEA3C, "layers": 0xF156, "hide": 0xED1A, "view": 0xE890,
    "bookmark": 0xE8A4, "more": 0xE712, "upload": 0xE898, "download": 0xE896,
    "error": 0xEA39, "sync": 0xE895, "open_file": 0xE8E5, "settings": 0xE713,
    "lock": 0xE72E, "text": 0xE8D2, "find": 0xE721,
}

_icon_font_path = next((p for p in ICON_FONT_PATHS if os.path.exists(p)), None)
_icon_cache = {}


def _render_glyph(codepoint, px, color):
    fuente = ImageFont.truetype(_icon_font_path, px)
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((px / 2, px / 2), chr(codepoint), font=fuente, fill=color, anchor="mm")
    return img


def icon(name, size=16, color="text"):
    """
    Devuelve un CTkImage con el ícono, o None si la fuente de íconos no está disponible
    (en ese caso los botones muestran solo texto).
    """
    if _icon_font_path is None or name not in GLYPHS:
        return None
    colores = C.get(color, color)
    if not isinstance(colores, (tuple, list)):
        colores = (colores, colores)
    clave = (name, size, tuple(colores))
    if clave not in _icon_cache:
        px = size * 4  # Alta resolución para que se vea nítido con cualquier escalado
        try:
            claro = _render_glyph(GLYPHS[name], px, colores[0])
            oscuro = _render_glyph(GLYPHS[name], px, colores[1])
        except OSError:
            return None
        _icon_cache[clave] = ctk.CTkImage(light_image=claro, dark_image=oscuro, size=(size, size))
    return _icon_cache[clave]


def icon_badge(name, diameter=110, icon_size=42, color="accent_text", background="accent_soft"):
    """Ícono dentro de un círculo de color, dibujado en la propia imagen (variante clara y oscura)."""
    if _icon_font_path is None or name not in GLYPHS:
        return None
    clave = ("badge", name, diameter, icon_size, color, background)
    if clave not in _icon_cache:
        escala = 3
        lado = diameter * escala
        variantes = []
        for i in (0, 1):
            img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
            ImageDraw.Draw(img).ellipse((0, 0, lado - 1, lado - 1), fill=C[background][i])
            glifo = _render_glyph(GLYPHS[name], icon_size * escala, C[color][i])
            img.alpha_composite(glifo, ((lado - glifo.width) // 2, (lado - glifo.height) // 2))
            variantes.append(img)
        _icon_cache[clave] = ctk.CTkImage(light_image=variantes[0], dark_image=variantes[1], size=(diameter, diameter))
    return _icon_cache[clave]


def has_icons():
    return _icon_font_path is not None


# ----------------------------------------------------
# Marca: logo e ícono de la app (generados con tools/build_assets.py)
# ----------------------------------------------------
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_brand_cache = {}


def asset_path(nombre):
    return os.path.join(ASSETS_DIR, nombre)


def brand_image(kind, height):
    """
    CTkImage del logo ("logo") o del ícono ("icon") con su variante para modo oscuro.
    Devuelve None si faltan los archivos.
    """
    clave = (kind, height)
    if clave not in _brand_cache:
        try:
            claro = Image.open(asset_path(f"{kind}_light.png" if kind == "logo" else "icon.png"))
            oscuro = Image.open(asset_path(f"{kind}_dark.png" if kind == "logo" else "icon_dark.png"))
        except OSError:
            return None
        ancho = round(claro.width * height / claro.height)
        _brand_cache[clave] = ctk.CTkImage(light_image=claro, dark_image=oscuro, size=(ancho, height))
    return _brand_cache[clave]


def shuriken_frames(size, pasos=9):
    """
    Cuadros de la estrella ninja girando (para el indicador de progreso).
    Tiene simetría de 90°, así que con 9 pasos de 10° la animación es continua.
    """
    clave = ("shuriken", size, pasos)
    if clave not in _brand_cache:
        try:
            base = Image.open(asset_path("shuriken.png")).convert("RGBA")
        except OSError:
            return []
        cuadros = []
        for i in range(pasos):
            girada = base.rotate(-i * 90 / pasos, resample=Image.BICUBIC)
            cuadros.append(ctk.CTkImage(light_image=girada, dark_image=girada, size=(size, size)))
        _brand_cache[clave] = cuadros
    return _brand_cache[clave]


def window_icon_path():
    ruta = asset_path("icon.ico")
    return ruta if os.path.exists(ruta) else None


def apply_window_icon(window):
    """
    Pone el ícono de la app en la ventana principal antes de que CustomTkinter ponga el suyo.
    Con default= también lo heredan los diálogos y ventanas secundarias.
    """
    ruta = window_icon_path()
    if ruta and os.name == "nt":
        try:
            window.iconbitmap(ruta, default=ruta)
        except Exception:
            pass
