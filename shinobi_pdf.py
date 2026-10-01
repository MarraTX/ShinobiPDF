"""
Punto de entrada de Shinobi.pdf.

Se le pueden pasar archivos al abrirlo (así funciona el «Dividir con Shinobi.pdf» del Explorador):
    python shinobi_pdf.py documento.pdf
"""
import sys

from shinobi.app import App


def main(argv=None):
    archivos = (sys.argv[1:] if argv is None else argv)
    app = App(files=archivos)
    app.mainloop()


if __name__ == "__main__":
    main()
