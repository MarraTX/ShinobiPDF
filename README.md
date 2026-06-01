# PDF Splitter Pro 📄✂️

Una herramienta de escritorio moderna, rápida y portátil para dividir documentos PDF en capítulos o rangos de páginas específicos. Diseñada con una estética oscura (*Dark Mode*) y enfocada en ofrecer la mejor experiencia de usuario.

## ✨ Características Principales

*   **Visor PDF Integrado en Tiempo Real:** Previsualiza el documento completo directamente en la aplicación sin necesidad de programas externos (potenciado por `PyMuPDF`).
*   **División por Capítulos:** Permite definir múltiples segmentos (ej. *Introducción*, *Capítulo 1*, *Conclusión*) especificando la página de inicio y fin para cada uno.
*   **Interfaz Gráfica Moderna:** UI responsiva, elegante y fluida construida con `CustomTkinter`.
*   **Totalmente Portable:** No requiere instalación. Descargas el `.exe` (o el `.zip`) y comienza a funcionar de inmediato.
*   **Atajos de Teclado:** Navegación rápida de páginas en el visor usando las flechas del teclado (◀ y ▶).
*   **Procesamiento Asíncrono:** La interfaz gráfica nunca se congela, permitiéndote ver el progreso de corte en tiempo real.

## 🚀 Descarga y Uso (Para Usuarios Finales)

Si solo quieres usar la aplicación para dividir tus PDFs, no necesitas conocimientos de programación.
1. Ve a la sección de **[Releases](../../releases)** a la derecha de esta página.
2. Descarga el archivo `PDF_Splitter_Pro_Windows.zip` de la última versión.
3. Descomprime el archivo en tu computadora y haz doble clic en `PDF Splitter Pro.exe`.

## 💻 Instalación Local (Para Desarrolladores)

Si deseas modificar el código o contribuir al proyecto, estos son los pasos para ejecutar el entorno de desarrollo:

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/pdf-splitter.git
cd pdf-splitter
```

### 2. Instalar dependencias
Asegúrate de tener Python 3.8 o superior instalado.
```bash
pip install -r requirements.txt
```
*(Nota: Las librerías principales son `customtkinter`, `pypdf`, `PyMuPDF` y `Pillow`)*

### 3. Ejecutar la aplicación
```bash
python pdf_splitter.py
```

### 4. Compilar Ejecutable (.exe)
Para generar el archivo portátil usando PyInstaller, ejecuta:
```bash
pyinstaller --noconfirm --onedir --windowed --noconsole --name "PDF Splitter Pro" --collect-all customtkinter --collect-all pymupdf pdf_splitter.py
```

## 🛠 Tecnologías Utilizadas
*   **[Python 3](https://www.python.org/)** - Lenguaje principal.
*   **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)** - Interfaz gráfica de usuario moderna.
*   **[PyMuPDF (fitz)](https://pymupdf.readthedocs.io/)** - Renderizado de imágenes de PDF de alta resolución.
*   **[pypdf](https://pypdf.readthedocs.io/)** - Motor de división y escritura de los PDFs.
*   **[PyInstaller](https://pyinstaller.org/)** - Empaquetado para Windows.

---
**Desarrollado para facilitar el manejo de documentos PDF de forma local, rápida y sin depender de servicios en la nube que comprometan tu privacidad.**
