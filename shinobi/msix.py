"""
Detección de la versión de Microsoft Store (paquete MSIX).

Cuando la app corre empaquetada:
- La Store se encarga de las actualizaciones: no se consulta GitHub (lo exigen las políticas de la Store).
- El «Dividir con Shinobi.pdf» del menú contextual lo declara el manifiesto del paquete, no el registro.
"""
import functools

APPMODEL_ERROR_NO_PACKAGE = 15700


@functools.lru_cache(maxsize=None)
def is_packaged():
    """True si el proceso tiene identidad de paquete (instalado desde la Store o con un .msix)."""
    try:
        import ctypes
        largo = ctypes.c_uint32(0)
        resultado = ctypes.windll.kernel32.GetCurrentPackageFullName(ctypes.byref(largo), None)
    except (AttributeError, OSError):  # No es Windows, o es anterior a Windows 8
        return False
    # Con un búfer vacío devuelve ERROR_INSUFFICIENT_BUFFER si hay paquete y APPMODEL_ERROR_NO_PACKAGE si no
    return resultado != APPMODEL_ERROR_NO_PACKAGE
