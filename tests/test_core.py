import os
import threading

import pytest
from pypdf import PdfReader

from shinobi import core
from shinobi.core import PasswordError, PlanError


def paginas(ruta):
    return len(PdfReader(ruta).pages)


# ----------------------------------------------------
# Nombres de archivo
# ----------------------------------------------------
@pytest.mark.parametrize("nombre, esperado", [
    ("Cap 1: Intro/Parte?", "Cap_1_IntroParte.pdf"),
    ("CON", "_CON.pdf"),
    ("   ", "capitulo.pdf"),
    ("final. ", "final.pdf"),
])
def test_nombre_archivo_seguro(nombre, esperado):
    assert core.nombre_archivo_seguro(nombre) == esperado


def test_nombres_numerados():
    plan = [("a", [0]), ("b", [1])]
    assert core.nombres_de_salida(plan, numerar=True) == ["01_a.pdf", "02_b.pdf"]


# ----------------------------------------------------
# Rangos y planes
# ----------------------------------------------------
def test_parse_ranges():
    assert core.parse_ranges("1-3, 5, 8-", 12) == [(1, 3), (5, 5), (8, 12)]
    assert core.parse_ranges("-2", 12) == [(1, 2)]


@pytest.mark.parametrize("texto", ["", "a", "5-3", "1-20", "0"])
def test_parse_ranges_invalidos(texto):
    with pytest.raises(PlanError):
        core.parse_ranges(texto, 12)


def test_plan_cada_n():
    plan = core.build_plan({"mode": "every", "n": 5, "name": "P"}, 12)
    assert [n for n, _ in plan] == ["P 1", "P 2", "P 3"]
    assert plan[-1][1] == [10, 11]


def test_plan_rangos_nombres_unicos_y_un_solo_archivo():
    plan = core.build_plan({"mode": "ranges", "text": "5, 5", "name": "E"}, 12)
    assert [n for n, _ in plan] == ["E 5", "E 5 (2)"]
    unico = core.build_plan({"mode": "ranges", "text": "1-2, 5", "single_file": True, "name": "E"}, 12)
    assert unico == [("E", [0, 1, 4])]


def test_plan_por_tamano():
    plan = core.build_plan({"mode": "size", "max_mb": 0.001}, 4, [600, 600, 2000, 100])
    assert [p for _, p in plan] == [[0], [1], [2], [3]]


def test_plan_capitulos_invalido():
    with pytest.raises(PlanError):
        core.build_plan({"mode": "chapters", "chapters": [["A", 3, 20]]}, 12)
    with pytest.raises(PlanError):
        core.build_plan({"mode": "chapters", "chapters": [["A", 1, 2], ["a", 3, 4]]}, 12)


def test_capitulos_desde_indice_baja_de_nivel():
    toc = [[1, "Libro", 1], [2, "Intro", 1], [2, "Cap", 3], [2, "Cap", 7]]
    assert core.capitulos_desde_indice(toc, 12) == [("Intro", 1, 2), ("Cap", 3, 6), ("Cap (2)", 7, 12)]


# ----------------------------------------------------
# Palabra clave
# ----------------------------------------------------
TEXTOS = ["Resumen", "Factura N 0001\nCliente", "detalle", "factura n 0002", "Factura N 0003"]


def test_paginas_con_texto_ignora_mayusculas_y_espacios():
    assert core.paginas_con_texto(TEXTOS, "factura  n") == [1, 3, 4]
    assert core.paginas_con_texto(TEXTOS, "Factura N", mayusculas=True) == [1, 4]


def test_plan_palabra_clave():
    spec = {"mode": "keyword", "text": "Factura N", "name_from_match": True, "include_before": True}
    plan = core.build_plan(spec, 5, textos_pagina=TEXTOS)
    assert [n for n, _ in plan] == ["Parte inicio", "Factura N 0001", "factura n 0002", "Factura N 0003"]
    assert [p for _, p in plan] == [[0], [1, 2], [3], [4]]


def test_plan_palabra_clave_sin_paginas_previas():
    spec = {"mode": "keyword", "text": "Factura", "include_before": False, "name": "F"}
    plan = core.build_plan(spec, 5, textos_pagina=TEXTOS)
    assert [n for n, _ in plan] == ["F 1", "F 2", "F 3"]


def test_plan_palabra_clave_sin_resultados():
    with pytest.raises(PlanError):
        core.build_plan({"mode": "keyword", "text": "Recibo"}, 5, textos_pagina=TEXTOS)


# ----------------------------------------------------
# Dividir, lote y unir con archivos reales
# ----------------------------------------------------
def test_split_capitulos_con_opciones(libro, tmp_path):
    salida = tmp_path / "out"
    spec = {"mode": "chapters", "chapters": [["Intro", 1, 2], ["Cap Uno", 3, 6], ["Cap Dos", 7, 12]]}
    generados, errores, cancelado = core.split_pdf(
        libro, spec, str(salida), {"numbering": True, "bookmarks": True, "compress": True},
        rotaciones={0: 90}, excluidas={4})
    assert (generados, errores, cancelado) == (3, [], False)
    assert sorted(os.listdir(salida)) == ["01_Intro.pdf", "02_Cap_Uno.pdf", "03_Cap_Dos.pdf"]

    cap_uno = PdfReader(salida / "02_Cap_Uno.pdf")
    assert len(cap_uno.pages) == 3  # 4 páginas menos la excluida
    assert cap_uno.metadata.title == "Cap Uno"
    assert core.leer_marcadores(cap_uno) == [(1, "Cap Uno", 0), (2, "Sub 1.1", 1)]
    assert PdfReader(salida / "01_Intro.pdf").pages[0].rotation == 90


def test_split_palabra_clave_extrae_texto(facturas, tmp_path):
    spec = {"mode": "keyword", "text": "Factura N", "name_from_match": True}
    generados, errores, _ = core.split_pdf(facturas, spec, str(tmp_path / "f"))
    assert errores == [] and generados == 4
    assert paginas(tmp_path / "f" / "Factura_N_0003.pdf") == 3


def test_split_cancelado(libro, tmp_path):
    cancel = threading.Event()
    cancel.set()
    assert core.split_pdf(libro, {"mode": "every", "n": 2}, str(tmp_path / "c"), cancel=cancel) == (0, [], True)


def test_pdf_protegido(protegido, tmp_path):
    with pytest.raises(PasswordError):
        core.abrir_lector(protegido)
    with pytest.raises(PasswordError):
        core.abrir_lector(protegido, "mal")
    generados, errores, _ = core.split_pdf(protegido, {"mode": "every", "n": 2}, str(tmp_path / "p"), password="secreto")
    assert (generados, errores) == (2, [])
    # Los archivos generados quedan sin contraseña
    assert not PdfReader(tmp_path / "p" / "Parte_1.pdf").is_encrypted


def test_lote(libro, facturas, protegido, tmp_path):
    raiz = tmp_path / "lote"
    generados, errores, cancelado, carpetas = core.batch_split(
        [libro, facturas, protegido], {"mode": "ranges", "text": "1-2"}, str(raiz), passwords={protegido: "secreto"})
    assert (generados, errores, cancelado) == (3, [], False)
    assert sorted(os.listdir(raiz)) == ["facturas_dividido", "libro_dividido", "protegido_dividido"]


def test_unir(libro, protegido, tmp_path):
    salida = tmp_path / "unido.pdf"
    ok, errores, _ = core.merge_pdfs([libro, protegido], str(salida), {"bookmark_per_file": True},
                                     passwords={protegido: "secreto"})
    assert ok and errores == []
    lector = PdfReader(salida)
    assert len(lector.pages) == 16
    assert [t for _, t, _ in core.leer_marcadores(lector)][:1] == ["libro"]


def test_unir_archivo_inexistente(tmp_path):
    ok, errores, _ = core.merge_pdfs([str(tmp_path / "no.pdf")], str(tmp_path / "x.pdf"))
    assert not ok and errores


def test_nombres_en_ingles(libro, tmp_path):
    from shinobi import i18n
    i18n.set_language("en")
    plan = core.build_plan({"mode": "every", "n": 6}, 12)
    assert [n for n, _ in plan] == ["Part 1", "Part 2"]
    _, errores, _, carpetas = core.batch_split([libro], {"mode": "every", "n": 6}, str(tmp_path))
    assert errores == [] and os.path.basename(carpetas[0]) == "libro_split"
    with pytest.raises(PlanError, match="isn't valid"):
        core.parse_ranges("1-99", 12)
