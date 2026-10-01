"""Verifica que todos los idiomas tengan los mismos textos y que el código no use claves inexistentes."""
import json
import os
import re
import string

import pytest

from shinobi import i18n

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODIGO = os.path.join(RAIZ, "shinobi")
# Claves que el código arma de forma indirecta (no aparecen como t("..."))
INDIRECTAS = {f"mode_{m}" for m in ("chapters", "every", "ranges", "size", "keyword")} \
    | {f"nav_{m}" for m in ("split", "merge", "images", "batch")} \
    | {f"quality_{m}" for m in ("low", "medium", "high")}


def catalogo(idioma):
    with open(os.path.join(i18n.LOCALES_DIR, f"{idioma}.json"), encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def claves_usadas():
    usadas = set(INDIRECTAS)
    for archivo in os.listdir(CODIGO):
        if archivo.endswith(".py"):
            texto = open(os.path.join(CODIGO, archivo), encoding="utf-8").read()
            usadas |= set(re.findall(r"""\bt\(["']([a-z_]+)["']""", texto))
    return usadas


def campos(valor):
    textos = valor.values() if isinstance(valor, dict) else [valor]
    return {f for texto in textos for _, f, _, _ in string.Formatter().parse(texto) if f}


@pytest.mark.parametrize("idioma", list(i18n.LANGUAGES))
def test_catalogo_completo(idioma):
    faltan = claves_usadas() - set(catalogo(idioma))
    assert not faltan, f"Faltan en {idioma}.json: {sorted(faltan)}"


@pytest.mark.parametrize("idioma", [i for i in i18n.LANGUAGES if i != i18n.DEFAULT_LANGUAGE])
def test_mismos_marcadores_que_ingles(idioma):
    base = catalogo(i18n.DEFAULT_LANGUAGE)
    otro = catalogo(idioma)
    assert set(base) == set(otro)
    for clave in base:
        assert campos(base[clave]) == campos(otro[clave]), clave


def test_plural_y_formato():
    i18n.set_language("en")
    assert i18n.t("files_count", n=1) == "1 file"
    assert i18n.t("files_count", n=3) == "3 files"
    i18n.set_language("es")
    assert i18n.t("pages_count", n=2) == "2 páginas"
    assert i18n.t("clave_inexistente") == "clave_inexistente"
