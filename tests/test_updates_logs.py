import os
import urllib.parse

import pytest

from shinobi import logs, updates


@pytest.mark.parametrize("remota, local, esperado", [
    ("v1.1", "1.0", True),
    ("1.0.1", "1.0", True),
    ("v1.0", "1.0", False),
    ("1.0", "1.0.0", False),
    ("v0.9", "1.0", False),
    ("v2.0-beta", "1.9", True),
    ("v1.10", "1.9", True),
])
def test_is_newer(remota, local, esperado):
    assert updates.is_newer(remota, local) is esperado


def test_reporte_oculta_el_usuario_y_respeta_el_largo(monkeypatch):
    casa = os.path.expanduser("~")
    monkeypatch.setattr(logs, "recent_lines", lambda cantidad=40: logs._anonimizar(f"Error abriendo {casa}\\Documentos\\a.pdf\n" * 400))
    url = logs.report_url("Error: prueba", "detalle")
    assert len(url) <= 7600
    cuerpo = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["body"][0]
    assert os.path.basename(casa) not in cuerpo
    assert "~" in cuerpo
