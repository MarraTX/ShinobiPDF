"""
Registro de errores y reporte de problemas.

Los errores se guardan en %APPDATA%/ShinobiPDF/logs/shinobi.log (rota a los 1 MB, guarda 3 archivos).
"Reportar un problema" abre un issue de GitHub completado con la versión, el sistema y las últimas
líneas del registro, con las rutas personales ocultas.
"""
import logging
import logging.handlers
import os
import platform
import re
import sys
import urllib.parse
import webbrowser

from . import APP_NAME, APP_VERSION, REPO_URL
from .settings import CONFIG_DIR

LOG_DIR = os.path.join(CONFIG_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "shinobi.log")

log = logging.getLogger("shinobi")


def setup():
    """Configura el registro en archivo. Si no se puede escribir, la app sigue funcionando igual."""
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        manejador = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(manejador)
    except OSError:
        log.addHandler(logging.NullHandler())
    log.info("%s %s iniciado (%s, Python %s)", APP_NAME, APP_VERSION, platform.platform(), platform.python_version())


def system_info():
    empaquetado = "exe" if getattr(sys, "frozen", False) else "python"
    return f"{APP_NAME} {APP_VERSION} ({empaquetado}) · {platform.platform()} · Python {platform.python_version()}"


def _anonimizar(texto):
    """Reemplaza la carpeta del usuario por ~ para no publicar su nombre en el issue."""
    inicio = os.path.expanduser("~")
    texto = texto.replace(inicio, "~").replace(inicio.replace("\\", "/"), "~")
    return re.sub(r"(?i)([A-Z]:\\Users\\)[^\\\s]+", r"\1<usuario>", texto)


def recent_lines(cantidad=40):
    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
            return _anonimizar("".join(f.readlines()[-cantidad:]))
    except OSError:
        return ""


def report_url(titulo="", detalle=""):
    cuerpo = (f"**Qué pasó / Qué esperabas que pasara:**\n\n{detalle}\n\n"
              f"**Sistema:** {system_info()}\n\n"
              f"<details><summary>Registro</summary>\n\n```\n{recent_lines()}\n```\n</details>\n")
    # Las URLs muy largas fallan en el navegador: se recorta el cuerpo si hace falta
    url = f"{REPO_URL}/issues/new?" + urllib.parse.urlencode({"title": titulo, "body": cuerpo})
    while len(url) > 7500 and len(cuerpo) > 500:
        cuerpo = cuerpo[:len(cuerpo) // 2] + "\n```\n</details>\n"
        url = f"{REPO_URL}/issues/new?" + urllib.parse.urlencode({"title": titulo, "body": cuerpo})
    return url


def open_report(titulo="", detalle=""):
    webbrowser.open(report_url(titulo, detalle))


def open_log_folder():
    os.makedirs(LOG_DIR, exist_ok=True)
    if os.name == "nt":
        os.startfile(LOG_DIR)
