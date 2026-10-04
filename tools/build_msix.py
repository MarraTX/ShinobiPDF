"""
Empaqueta la app como MSIX para publicarla en Microsoft Store (requiere haber corrido antes tools/build_exe.py).

    python tools/build_msix.py    -> dist/ShinobiPDF.msix (y dist/msix/, el paquete sin comprimir)

- El paquete no se firma: al subirlo a Partner Center lo firma Microsoft.
- Identidad del paquete: installer/msix/store_identity.json (se copia de Partner Center > Identidad del producto).
- Para probarlo en tu PC sin firmar (con el Modo de desarrollador de Windows activado):
      Add-AppxPackage -Register dist\\msix\\AppxManifest.xml
- Usa makeappx.exe y makepri.exe del Windows SDK (vienen en los runners de GitHub Actions; en tu PC:
  winget install Microsoft.WindowsSDK.10.0.26100).
"""
import glob
import json
import os
import shutil
import string
import subprocess
import sys
import tempfile

from PIL import Image

from build_exe import borrar_con_reintentos

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from shinobi import APP_VERSION, EXE_NAME  # noqa: E402

MSIX = os.path.join(RAIZ, "installer", "msix")
ASSETS = os.path.join(RAIZ, "shinobi", "assets")
DIST = os.path.join(RAIZ, "dist")
IDENTIDAD_DE_EJEMPLO = "ShinobiPDF.Dev"

# Logos que pide el manifiesto: nombre -> lista de (calificador, ancho, alto, fracción que ocupa el ninja)
# Ver https://learn.microsoft.com/windows/apps/design/style/iconography/app-icon-construction
LOGOS = {
    "Square44x44Logo": [(f"scale-{e}", 44 * e // 100, 44 * e // 100, 0.92) for e in (100, 200, 400)]
                       + [(f"targetsize-{t}{alt}", t, t, 1.0) for t in (16, 24, 32, 48, 256)
                          for alt in ("", "_altform-unplated")],
    "Square150x150Logo": [(f"scale-{e}", 150 * e // 100, 150 * e // 100, 0.66) for e in (100, 200)],
    "Wide310x150Logo": [(f"scale-{e}", 310 * e // 100, 150 * e // 100, 0.66) for e in (100, 200)],
    "StoreLogo": [(f"scale-{e}", 50 * e // 100, 50 * e // 100, 1.0) for e in (100, 200, 400)],
}


def version_msix():
    """'1.2' -> '1.2.0.0'. La Store exige 4 números y que el último sea 0."""
    numeros = [int(p) for p in APP_VERSION.split(".")][:3]
    return ".".join(map(str, numeros + [0] * (4 - len(numeros))))


def buscar_herramienta(nombre):
    """Busca una herramienta del Windows SDK (la versión más nueva instalada)."""
    if shutil.which(nombre):
        return shutil.which(nombre)
    kits = os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Windows Kits", "10", "bin")
    candidatos = glob.glob(os.path.join(kits, "10.*", "x64", nombre))
    if not candidatos:
        sys.exit(f"No se encontró {nombre} del Windows SDK. Instalalo con:  winget install Microsoft.WindowsSDK.10.0.26100")
    return max(candidatos, key=lambda ruta: tuple(int(n) for n in ruta.split(os.sep)[-3].split(".")))


def leer_identidad():
    with open(os.path.join(MSIX, "store_identity.json"), encoding="utf-8") as f:
        identidad = json.load(f)
    if identidad["identity_name"] == IDENTIDAD_DE_EJEMPLO:
        print("AVISO: installer/msix/store_identity.json tiene la identidad de ejemplo. El paquete sirve para "
              "probar en tu PC, pero la Store lo va a rechazar hasta que copies la de Partner Center.\n")
    return identidad


def generar_logos(carpeta):
    os.makedirs(carpeta, exist_ok=True)
    # La variante con contorno claro (la del .ico) se distingue sobre fondos claros y oscuros
    ninja = Image.open(os.path.join(ASSETS, "icon_dark.png")).convert("RGBA")
    for nombre, variantes in LOGOS.items():
        for calificador, ancho, alto, fraccion in variantes:
            lado = round(min(ancho, alto) * fraccion)
            lienzo = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
            lienzo.alpha_composite(ninja.resize((lado, lado), Image.LANCZOS), ((ancho - lado) // 2, (alto - lado) // 2))
            lienzo.save(os.path.join(carpeta, f"{nombre}.{calificador}.png"))


def escribir_manifiesto(destino, identidad):
    with open(os.path.join(MSIX, "AppxManifest.xml"), encoding="utf-8") as f:
        plantilla = string.Template(f.read())
    contenido = plantilla.substitute(identidad, version=version_msix(), exe=EXE_NAME + ".exe")
    with open(destino, "w", encoding="utf-8") as f:
        f.write(contenido)


def generar_pri(carpeta_paquete, temporal):
    """
    resources.pri: índice de los textos traducidos (ms-resource:) y de los logos en varios tamaños.
    Se indexa una copia con solo Assets y Strings para no recorrer los miles de archivos de PyInstaller.
    """
    makepri = buscar_herramienta("makepri.exe")
    recursos = os.path.join(temporal, "recursos")
    shutil.copytree(os.path.join(carpeta_paquete, "Assets"), os.path.join(recursos, "Assets"))
    shutil.copytree(os.path.join(MSIX, "Strings"), os.path.join(recursos, "Strings"))
    config = os.path.join(temporal, "priconfig.xml")
    subprocess.run([makepri, "createconfig", "/cf", config, "/dq", "en-US", "/pv", "10.0.0", "/o"], check=True)
    subprocess.run([makepri, "new", "/pr", recursos, "/cf", config,
                    "/mn", os.path.join(carpeta_paquete, "AppxManifest.xml"),
                    "/of", os.path.join(carpeta_paquete, "resources.pri"), "/o"], check=True)


def main():
    programa = os.path.join(DIST, EXE_NAME)
    if not os.path.exists(os.path.join(programa, EXE_NAME + ".exe")):
        sys.exit("Falta el ejecutable: corré primero  python tools/build_exe.py")
    identidad = leer_identidad()

    paquete = os.path.join(DIST, "msix")
    borrar_con_reintentos(paquete)
    shutil.copytree(programa, paquete)
    generar_logos(os.path.join(paquete, "Assets"))
    escribir_manifiesto(os.path.join(paquete, "AppxManifest.xml"), identidad)
    with tempfile.TemporaryDirectory() as temporal:
        generar_pri(paquete, temporal)

    salida = os.path.join(DIST, "ShinobiPDF.msix")
    subprocess.run([buscar_herramienta("makeappx.exe"), "pack", "/d", paquete, "/p", salida, "/o"], check=True)
    print(f"\nPaquete listo: {salida}  (versión {version_msix()})")
    print(f"Para probarlo sin firmar:  Add-AppxPackage -Register \"{os.path.join(paquete, 'AppxManifest.xml')}\"")


if __name__ == "__main__":
    main()
