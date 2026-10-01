"""Preferencias del usuario guardadas en %APPDATA%/ShinobiPDF/config.json."""
import json
import os

from . import APP_ID

_APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")
CONFIG_DIR = os.path.join(_APPDATA, APP_ID)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
# Configuración de cuando la app se llamaba "PDF Splitter Pro" (se importa una sola vez)
LEGACY_CONFIG_FILE = os.path.join(_APPDATA, "PDF Splitter Pro", "config.json")
MAX_RECIENTES = 8

DEFAULTS = {
    "theme": "dark",
    "language": None,  # None = usar el del instalador o el de Windows
    "recent": [],
    "options": {"numbering": False, "bookmarks": True, "compress": False},
    "onboarding_done": False,   # Ya se mostró el tour de bienvenida
    "last_version": None,       # Última versión abierta (para mostrar las novedades al actualizar)
    "check_updates": True,
    "last_update_check": 0,
}


class Settings:
    def __init__(self, path=CONFIG_FILE):
        self.path = path
        self.data = json.loads(json.dumps(DEFAULTS))  # copia profunda
        origen = path if os.path.exists(path) or path != CONFIG_FILE else LEGACY_CONFIG_FILE
        try:
            with open(origen, encoding="utf-8") as f:
                guardado = json.load(f)
            if isinstance(guardado, dict):
                self.data.update(guardado)
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass  # No poder guardar preferencias no debe romper la app

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def recent_files(self):
        return [r for r in self.data.get("recent", []) if isinstance(r, str) and os.path.exists(r)]

    def add_recent(self, path):
        path = os.path.normpath(path)
        recientes = [r for r in self.data.get("recent", []) if os.path.normcase(r) != os.path.normcase(path)]
        self.set("recent", [path] + recientes[:MAX_RECIENTES - 1])
