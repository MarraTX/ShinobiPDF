"""
Compila el instalador con Inno Setup 6 (requiere haber corrido antes tools/build_exe.py).

    python tools/build_installer.py    -> dist/ShinobiPDF-Setup.exe

El nombre no lleva versión a propósito: así el enlace de descarga de la web puede apuntar siempre a
https://github.com/<usuario>/<repo>/releases/latest/download/ShinobiPDF-Setup.exe
"""
import os
import shutil
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from shinobi import APP_PUBLISHER, APP_VERSION, EXE_NAME, REPO_URL  # noqa: E402


def buscar_iscc():
    candidatos = [
        shutil.which("iscc"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Inno Setup 6", "ISCC.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Inno Setup 6", "ISCC.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
    ]
    return next((c for c in candidatos if c and os.path.exists(c)), None)


def main():
    if not os.path.exists(os.path.join(RAIZ, "dist", EXE_NAME, EXE_NAME + ".exe")):
        sys.exit("Falta el ejecutable: corré primero  python tools/build_exe.py")
    iscc = buscar_iscc()
    if not iscc:
        sys.exit("No se encontró Inno Setup 6. Instalalo desde https://jrsoftware.org/isdl.php "
                 "o con:  winget install JRSoftware.InnoSetup")
    subprocess.run([iscc, f"/DAppVersion={APP_VERSION}", f"/DAppPublisher={APP_PUBLISHER}", f"/DAppUrl={REPO_URL}",
                    os.path.join(RAIZ, "installer", "shinobi.iss")], check=True)
    print(f"\nInstalador listo: {os.path.join(RAIZ, 'dist', 'ShinobiPDF-Setup.exe')}")


if __name__ == "__main__":
    main()
