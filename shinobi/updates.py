"""
Búsqueda de actualizaciones en GitHub Releases.

Consulta https://api.github.com/repos/<repo>/releases/latest en un hilo aparte. No descarga nada:
si hay una versión más nueva, la app avisa y abre la página de la versión para descargarla.
"""
import json
import re
import threading
import time
import urllib.error
import urllib.request

from . import APP_NAME, APP_VERSION, GITHUB_REPO

API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
INTERVALO = 24 * 60 * 60  # Como mucho una consulta automática por día


def parse_version(texto):
    """'v1.2.3' -> (1, 2, 3). Ignora sufijos como '-beta'."""
    numeros = re.findall(r"\d+", (texto or "").split("-")[0])
    return tuple(int(n) for n in numeros[:4]) or (0,)


def is_newer(remota, local=APP_VERSION):
    a, b = parse_version(remota), parse_version(local)
    largo = max(len(a), len(b))
    return a + (0,) * (largo - len(a)) > b + (0,) * (largo - len(b))


def fetch_latest(timeout=6):
    """Devuelve {"version", "url", "notes"} de la última versión publicada, o lanza una excepción."""
    pedido = urllib.request.Request(API_URL, headers={"Accept": "application/vnd.github+json",
                                                      "User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(pedido, timeout=timeout) as respuesta:
        datos = json.load(respuesta)
    return {"version": datos.get("tag_name", "").lstrip("vV"), "url": datos.get("html_url", ""),
            "notes": datos.get("body") or ""}


def check_in_background(app, manual=False):
    """
    Busca actualizaciones sin bloquear la interfaz y le avisa a app.on_update_result(resultado, manual).
    resultado: dict de fetch_latest(), None si no hay novedades, o una Exception si falló.
    """
    ajustes = app.settings
    if not manual:
        if not ajustes.get("check_updates"):
            return
        if time.time() - (ajustes.get("last_update_check") or 0) < INTERVALO:
            return

    resultado = {}

    def trabajador():
        try:
            ultima = fetch_latest()
            resultado["valor"] = ultima if is_newer(ultima["version"]) else None
        except urllib.error.HTTPError as e:
            # 404 = el repo todavía no tiene versiones publicadas: no es un error
            resultado["valor"] = None if e.code == 404 else e
        except Exception as e:  # Sin internet, GitHub caído, límite de consultas, etc.
            resultado["valor"] = e

    hilo = threading.Thread(target=trabajador, daemon=True)
    hilo.start()

    # Tkinter solo debe tocarse desde el hilo principal: se revisa el resultado con after()
    def revisar():
        if hilo.is_alive():
            app.after(300, revisar)
            return
        valor = resultado.get("valor")
        if not isinstance(valor, Exception):
            ajustes.set("last_update_check", time.time())
        app.on_update_result(valor, manual)

    app.after(300, revisar)
