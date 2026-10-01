"""
Traducciones de la interfaz.

Los textos viven en shinobi/locales/<idioma>.json. Para agregar un idioma alcanza con copiar en.json,
traducirlo y sumarlo a LANGUAGES. Un valor puede ser un texto o, para plurales, {"one": ..., "other": ...}:

    t("files_count", n=3)  ->  "3 archivos"
"""
import json
import locale
import os

from . import APP_ID

LANGUAGES = {"es": "Español", "en": "English"}
DEFAULT_LANGUAGE = "en"
LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")

_textos = {}
_respaldo = {}
_idioma = DEFAULT_LANGUAGE


def _leer(idioma):
    try:
        with open(os.path.join(LOCALES_DIR, f"{idioma}.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def set_language(idioma):
    global _textos, _respaldo, _idioma
    _idioma = idioma if idioma in LANGUAGES else DEFAULT_LANGUAGE
    _textos = _leer(_idioma)
    _respaldo = _leer(DEFAULT_LANGUAGE) if _idioma != DEFAULT_LANGUAGE else {}


def current_language():
    return _idioma


def t(clave, **valores):
    """Texto traducido. Si falta en el idioma actual se usa inglés, y si no la propia clave."""
    texto = _textos.get(clave, _respaldo.get(clave, clave))
    if isinstance(texto, dict):
        texto = texto["one"] if valores.get("n") == 1 and "one" in texto else texto.get("other", clave)
    return texto.format(**valores) if valores else texto


def has(clave):
    """True si existe un texto para la clave (en el idioma actual o en inglés)."""
    return clave in _textos or clave in _respaldo


def _idioma_del_instalador():
    """Idioma elegido en el instalador (Inno Setup lo guarda en HKCU\\Software\\ShinobiPDF)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\{APP_ID}") as clave:
            valor = str(winreg.QueryValueEx(clave, "Language")[0]).lower()
    except (ImportError, OSError):
        return None
    return {"spanish": "es", "english": "en"}.get(valor, valor if valor in LANGUAGES else None)


def _idioma_del_sistema():
    try:
        import ctypes
        # Idioma de la interfaz de Windows: los 10 bits bajos son el idioma principal (0x0A = español)
        principal = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        return {0x0A: "es", 0x09: "en"}.get(principal)
    except (AttributeError, OSError):
        pass
    codigo = (locale.getlocale()[0] or "").lower()
    return "es" if codigo.startswith(("es", "spanish")) else None


def detect_language(guardado=None):
    """Idioma a usar: el elegido en la app, el del instalador o el de Windows (en ese orden)."""
    for candidato in (guardado, _idioma_del_instalador(), _idioma_del_sistema()):
        if candidato in LANGUAGES:
            return candidato
    return DEFAULT_LANGUAGE


set_language(DEFAULT_LANGUAGE)
