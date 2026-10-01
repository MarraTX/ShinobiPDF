"""
Compila el ejecutable portable con PyInstaller.

    python tools/build_exe.py          -> dist/Shinobi/Shinobi.exe
    python tools/build_exe.py --zip    -> además dist/ShinobiPDF-Portable.zip (para Releases)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from shinobi import APP_NAME, APP_PUBLISHER, APP_VERSION, EXE_NAME  # noqa: E402

ASSETS = os.path.join(RAIZ, "shinobi", "assets")
LOCALES = os.path.join(RAIZ, "shinobi", "locales")


def archivo_de_version(carpeta):
    """Datos que Windows muestra en Propiedades > Detalles del .exe."""
    numeros = [int(p) for p in APP_VERSION.split(".")][:4]
    numeros += [0] * (4 - len(numeros))
    version = tuple(numeros)
    contenido = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={version}, prodvers={version}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', {APP_PUBLISHER!r}),
      StringStruct('FileDescription', {APP_NAME!r}),
      StringStruct('FileVersion', {APP_VERSION!r}),
      StringStruct('InternalName', {EXE_NAME!r}),
      StringStruct('OriginalFilename', {EXE_NAME + '.exe'!r}),
      StringStruct('ProductName', {APP_NAME!r}),
      StringStruct('ProductVersion', {APP_VERSION!r})])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    ruta = os.path.join(carpeta, "version_info.txt")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)
    return ruta


def borrar_con_reintentos(carpeta, intentos=10):
    """Borra una carpeta reintentando unos segundos si OneDrive o el antivirus la tienen bloqueada."""
    for intento in range(intentos):
        if not os.path.exists(carpeta):
            return
        try:
            shutil.rmtree(carpeta)
            return
        except PermissionError:
            # OneDrive convierte las carpetas en "puntos de reanálisis" que shutil no puede borrar;
            # el comando de Windows sí
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", carpeta], capture_output=True)
                if not os.path.exists(carpeta):
                    return
            if intento == intentos - 1:
                raise SystemExit(f"No se pudo borrar {carpeta}: cerrá Shinobi si está abierto y probá de nuevo.")
            time.sleep(1)


def main():
    if not os.path.exists(os.path.join(ASSETS, "icon.ico")):
        sys.exit("Faltan los recursos de la marca: ejecutá primero  python tools/build_assets.py")

    # Se compila en la carpeta temporal del sistema y al final se copia a dist/: si el proyecto está
    # en OneDrive/Dropbox, la sincronización bloquea archivos y PyInstaller falla al reemplazarlos
    build = os.path.join(tempfile.gettempdir(), "shinobi-pdf-build")
    dist_temporal = os.path.join(build, "dist")
    os.makedirs(build, exist_ok=True)
    comando = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", EXE_NAME,
        "--icon", os.path.join(ASSETS, "icon.ico"),
        "--version-file", archivo_de_version(build),
        "--add-data", f"{ASSETS}{os.pathsep}shinobi/assets",
        "--add-data", f"{LOCALES}{os.pathsep}shinobi/locales",
        "--collect-all", "customtkinter",
        "--collect-all", "pymupdf",
        "--collect-all", "tkinterdnd2",
        "--hidden-import", "cryptography",  # pypdf lo usa para abrir PDFs cifrados con AES
        "--distpath", dist_temporal, "--workpath", build, "--specpath", build,
        os.path.join(RAIZ, "shinobi_pdf.py"),
    ]
    subprocess.run(comando, check=True, cwd=RAIZ)

    dist = os.path.join(RAIZ, "dist")
    carpeta = os.path.join(dist, EXE_NAME)
    borrar_con_reintentos(carpeta)
    shutil.copytree(os.path.join(dist_temporal, EXE_NAME), carpeta)
    # La AGPL exige distribuir el texto de la licencia junto al programa (portable e instalador)
    licencia = os.path.join(RAIZ, "LICENSE")
    if os.path.exists(licencia):
        shutil.copyfile(licencia, os.path.join(carpeta, "LICENSE.txt"))
    print(f"\nEjecutable listo: {os.path.join(carpeta, EXE_NAME + '.exe')}")

    if "--zip" in sys.argv:
        zip_base = os.path.join(dist, "ShinobiPDF-Portable")
        shutil.make_archive(zip_base, "zip", dist, EXE_NAME)
        print(f"Zip listo: {zip_base}.zip")


if __name__ == "__main__":
    main()
