<p align="center">
  <img src="shinobi/assets/logo_light.png" alt="Shinobi.pdf" width="440">
</p>

<p align="center"><b>Dividí, unií y convertí tus PDFs sin subirlos a ningún lado.</b><br>
Una app de escritorio rápida, libre y de código abierto. Tus archivos nunca salen de tu computadora.</p>

---

## ✨ Características

### Dividir
*   **Cinco formas de dividir:** por capítulos, cada N páginas, por rangos (`1-3, 5, 8-`), por tamaño máximo de archivo (ideal para mail) o **por texto**: un archivo nuevo en cada página que contiene, por ejemplo, «Factura N°», y cada archivo puede tomar su nombre de esa línea.
*   **Buscar texto en el visor (Ctrl+F):** resalta las coincidencias en la página y las marca en las miniaturas.
*   **Detección automática de capítulos** desde el índice (marcadores) del PDF.
*   **Marcado desde el visor:** "Usar como inicio" / "Usar como fin" asignan la página visible al capítulo seleccionado; el fin del capítulo anterior se completa solo.
*   **Miniaturas con colores:** cada capítulo tiene un color, y se ve de un vistazo qué páginas van a cada archivo.
*   **Rotar y excluir páginas** antes de exportar.
*   **Plantillas:** guardá y cargá la configuración como `.json`.
*   **Opciones de salida:** numerar archivos (`01_`, `02_`...), conservar marcadores y comprimir sin pérdida.

### Otras herramientas
*   **Unir PDFs** en el orden que elijas, con un marcador por archivo.
*   **Exportar páginas a imágenes** PNG o JPG en tres calidades.
*   **Procesar en lote:** aplicá la misma división a muchos PDFs a la vez.

### Experiencia
*   **En español e inglés.** El idioma se elige en el instalador y se puede cambiar desde *Ajustes*.
*   **PDFs con contraseña:** la app la pide al abrirlos (los archivos generados quedan sin contraseña).
*   **Clic derecho en el Explorador → "Dividir con Shinobi.pdf"**.
*   **Arrastrar y soltar**, archivos recientes, **modo claro y oscuro**.
*   **Interfaz responsiva:** se adapta al tamaño de la ventana y al zoom de Windows (125%, 150%...).
*   **Atajos de teclado:** ← → para cambiar de página, `Ctrl+F` buscar, `R` rotar, `X` excluir, `Ctrl+O` abrir.
*   **Aviso de actualizaciones:** la app avisa cuando hay una versión nueva (se puede desactivar en *Ajustes*).
*   **Tour de bienvenida** la primera vez y **novedades** después de cada actualización.
*   **Reportar un problema** desde la app: abre un issue con la versión y el registro de errores, sin datos personales.

## 🚀 Descarga

1. Entrá a **[Releases](../../releases/latest)**.
2. Descargá **`ShinobiPDF-Setup.exe`** (instalador) o **`ShinobiPDF-Portable.zip`** (sin instalación).
3. El instalador no pide permisos de administrador y te deja elegir el idioma.

## 💻 Desarrollo

```bash
git clone https://github.com/MarraTX/ShinobiPDF.git
cd ShinobiPDF
pip install -r requirements.txt -r requirements-dev.txt
python shinobi_pdf.py              # o:  python shinobi_pdf.py archivo.pdf
python -m pytest                   # tests
```

### Compilar
```bash
python tools/build_exe.py --zip    # dist/Shinobi/Shinobi.exe y dist/ShinobiPDF-Portable.zip
python tools/build_installer.py    # dist/ShinobiPDF-Setup.exe (requiere Inno Setup 6)
```
Si cambiás el logo o el ícono en `img/`, regenerá los recursos con `python tools/build_assets.py`.

### Publicar una versión
GitHub Actions corre los tests en cada push. Al crear un tag compila el `.exe` y el instalador, y los sube a Releases:
```bash
git tag v1.0
git push origin v1.0
```
Los archivos se publican sin número de versión en el nombre, así la web puede enlazar siempre a
`https://github.com/MarraTX/ShinobiPDF/releases/latest/download/ShinobiPDF-Setup.exe`.

### Traducciones
Los textos están en `shinobi/locales/<idioma>.json`. Para sumar un idioma: copiá `en.json`, traducilo y agregalo a `LANGUAGES` en `shinobi/i18n.py`. Los tests verifican que no falte ningún texto.

### Estructura del código
```
shinobi_pdf.py           Punto de entrada (acepta archivos como argumento)
shinobi/
  core.py                Lógica de PDFs (dividir, unir, lote, búsqueda) sin interfaz
  i18n.py, locales/      Traducciones
  app.py                 Ventana principal, barra lateral, tema, contraseñas y tareas en segundo plano
  split_view.py          Vista "Dividir" (visor, búsqueda, miniaturas, modos, capítulos)
  tools_views.py         Vistas "Unir", "A imágenes" y "Lote"
  widgets.py             Componentes reutilizables (botones, diálogos, avisos, miniaturas)
  settings_dialog.py     Ventanas de ajustes y «Acerca de»
  onboarding.py          Tour de bienvenida y novedades
  updates.py             Aviso de actualizaciones (GitHub Releases)
  logs.py                Registro de errores y reporte de problemas
  integration.py         Menú contextual del Explorador de Windows
  theme.py               Colores, tipografías, íconos y logo
  settings.py            Preferencias del usuario (%APPDATA%\ShinobiPDF)
  assets/                Logo, ícono y estrella generados desde img/
installer/               Script de Inno Setup e imágenes del asistente
tools/                   Scripts para generar recursos, compilar el .exe y el instalador
tests/                   Tests automáticos
```

## 🛠 Tecnologías
*   **[Python 3](https://www.python.org/)** y **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)** para la interfaz.
*   **[PyMuPDF](https://pymupdf.readthedocs.io/)** para renderizar páginas y buscar texto.
*   **[pypdf](https://pypdf.readthedocs.io/)** para dividir, unir y escribir los PDFs.
*   **[PyInstaller](https://pyinstaller.org/)** e **[Inno Setup](https://jrsoftware.org/isinfo.php)** para el ejecutable y el instalador.

## 📄 Licencia
Shinobi.pdf usa PyMuPDF, que se distribuye bajo **AGPL-3.0**, por lo que el proyecto se publica bajo esa misma licencia (ver `LICENSE`).
