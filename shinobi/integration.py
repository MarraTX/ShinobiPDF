"""
Integración con el Explorador de Windows: opción «Dividir con Shinobi.pdf» en el menú contextual de los PDF.

Se registra en HKEY_CURRENT_USER (solo para el usuario actual, sin permisos de administrador).
El instalador escribe la misma clave, así que el interruptor de Ajustes y el instalador están sincronizados.
"""
import os
import sys

from . import APP_ID
from .i18n import t

CLAVE_MENU = rf"Software\Classes\SystemFileAssociations\.pdf\shell\{APP_ID}"
# Clave usada cuando la app se llamaba "PDF Splitter Pro"; se borra al instalar la nueva
CLAVE_MENU_ANTERIOR = r"Software\Classes\SystemFileAssociations\.pdf\shell\PDFSplitterPro"

try:
    import winreg
except ImportError:  # No es Windows
    winreg = None


def available():
    return winreg is not None


def launch_command():
    """Comando que abre la app con el archivo elegido, tanto en el .exe como ejecutando con Python."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" "%1"', sys.executable
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(raiz, "shinobi_pdf.py")
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    interprete = pythonw if os.path.exists(pythonw) else sys.executable
    icono = os.path.join(raiz, "shinobi", "assets", "icon.ico")
    return f'"{interprete}" "{script}" "%1"', icono


def is_installed():
    if not available():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_MENU + r"\command"):
            return True
    except OSError:
        return False


def _borrar(clave_base):
    for subclave in (clave_base + r"\command", clave_base):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, subclave)
        except FileNotFoundError:
            pass


def install():
    _borrar(CLAVE_MENU_ANTERIOR)
    comando, icono = launch_command()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLAVE_MENU) as clave:
        winreg.SetValueEx(clave, "", 0, winreg.REG_SZ, t("context_menu_verb"))
        winreg.SetValueEx(clave, "Icon", 0, winreg.REG_SZ, icono)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLAVE_MENU + r"\command") as clave:
        winreg.SetValueEx(clave, "", 0, winreg.REG_SZ, comando)


def uninstall():
    _borrar(CLAVE_MENU)
    _borrar(CLAVE_MENU_ANTERIOR)
