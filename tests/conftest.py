import os
import sys

import fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shinobi import i18n  # noqa: E402


@pytest.fixture(autouse=True)
def idioma_espanol():
    """Los tests comparan nombres de archivo en español («Parte», «_dividido»)."""
    i18n.set_language("es")
    yield
    i18n.set_language("es")


def _nuevo_pdf(textos):
    doc = fitz.open()
    for texto in textos:
        pagina = doc.new_page()
        pagina.insert_text((72, 72), texto, fontsize=14)
    return doc


@pytest.fixture
def libro(tmp_path):
    """PDF de 12 páginas con índice de dos niveles."""
    doc = _nuevo_pdf([f"Pagina {i + 1}" for i in range(12)])
    doc.set_toc([[1, "Libro", 1], [2, "Intro", 1], [2, "Cap Uno", 3], [3, "Sub 1.1", 4], [2, "Cap Dos", 7]])
    ruta = tmp_path / "libro.pdf"
    doc.save(ruta)
    return str(ruta)


@pytest.fixture
def facturas(tmp_path):
    """PDF con tres facturas de distinta cantidad de páginas y una carátula."""
    doc = _nuevo_pdf([
        "Resumen del mes",
        "Factura N 0001\nCliente: Ana", "detalle",
        "Factura N 0002\nCliente: Beto",
        "Factura N 0003\nCliente: Caro", "detalle", "detalle",
    ])
    ruta = tmp_path / "facturas.pdf"
    doc.save(ruta)
    return str(ruta)


@pytest.fixture
def protegido(tmp_path):
    """PDF de 4 páginas cifrado con la contraseña «secreto»."""
    doc = _nuevo_pdf([f"Pagina {i + 1}" for i in range(4)])
    ruta = tmp_path / "protegido.pdf"
    doc.save(ruta, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secreto", owner_pw="dueno")
    return str(ruta)
