"""
Lógica de manejo de PDFs, independiente de la interfaz gráfica.

Una "especificación" (spec) describe cómo dividir un PDF y no depende de un documento
concreto, por eso se puede guardar como plantilla o aplicar a varios archivos:

    {"mode": "chapters", "chapters": [["Intro", 1, 3], ["Cap 1", 4, 10]]}
    {"mode": "every", "n": 10, "name": "Parte"}
    {"mode": "ranges", "text": "1-3, 5, 8-", "single_file": False, "name": "Extracto"}
    {"mode": "size", "max_mb": 10, "name": "Parte"}
    {"mode": "keyword", "text": "Factura N°", "case_sensitive": False, "name": "Parte",
     "name_from_match": True, "include_before": True}

build_plan() convierte una spec en un "plan": lista de (nombre, [índices de página 0-based]).
"""
import io
import os
import re

from pypdf import PdfReader, PdfWriter

from . import APP_NAME
from .i18n import t

# Caracteres no permitidos en nombres de archivo de Windows
CARACTERES_INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
NOMBRES_RESERVADOS = {"CON", "PRN", "AUX", "NUL",
                      *(f"COM{i}" for i in range(1, 10)),
                      *(f"LPT{i}" for i in range(1, 10))}

MODOS = ("chapters", "every", "ranges", "size", "keyword")


class PlanError(ValueError):
    """Error de configuración que se muestra tal cual al usuario."""


class PasswordError(PlanError):
    """El PDF está protegido y la contraseña falta o es incorrecta."""


def nombre_archivo_seguro(nombre):
    """
    Convierte el nombre de un capítulo en un nombre de archivo válido en Windows.
    """
    limpio = CARACTERES_INVALIDOS.sub("", nombre).strip().replace(" ", "_")
    limpio = limpio.rstrip(". ")
    if not limpio:
        limpio = t("default_filename")
    if limpio.upper() in NOMBRES_RESERVADOS:
        limpio = f"_{limpio}"
    return f"{limpio[:150]}.pdf"


def nombres_de_salida(plan, numerar=False):
    """Nombres de archivo finales para cada elemento del plan."""
    ancho = max(2, len(str(len(plan))))
    nombres = []
    for i, (nombre, _) in enumerate(plan, start=1):
        archivo = nombre_archivo_seguro(nombre)
        nombres.append(f"{i:0{ancho}d}_{archivo}" if numerar else archivo)
    return nombres


def formatear_tamano(num_bytes):
    for unidad in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unidad == "GB":
            return f"{num_bytes:.0f} {unidad}" if unidad == "B" else f"{num_bytes:.1f} {unidad}"
        num_bytes /= 1024


# ----------------------------------------------------
# Construcción del plan
# ----------------------------------------------------
def parse_ranges(texto, total):
    """
    Interpreta rangos como '1-3, 5, 8-10'. '8-' significa hasta el final y '-3' desde el principio.
    Devuelve una lista de tuplas (inicio, fin) 1-based.
    """
    partes = [p.strip() for p in re.split(r"[,;]", texto or "") if p.strip()]
    if not partes:
        raise PlanError(t("err_ranges_empty"))

    rangos = []
    for parte in partes:
        m = re.fullmatch(r"(\d+)?\s*-\s*(\d+)?|(\d+)", parte)
        if not m or (m.group(3) is None and m.group(1) is None and m.group(2) is None):
            raise PlanError(t("err_ranges_format", part=parte))
        if m.group(3):
            inicio = fin = int(m.group(3))
        else:
            inicio = int(m.group(1)) if m.group(1) else 1
            fin = int(m.group(2)) if m.group(2) else total
        if inicio < 1 or fin > total or inicio > fin:
            raise PlanError(t("err_range_invalid", part=parte, total=total))
        rangos.append((inicio, fin))
    return rangos


def _nombre_unico(nombre, usados):
    candidato, n = nombre, 2
    while nombre_archivo_seguro(candidato).lower() in usados:
        candidato = f"{nombre} ({n})"
        n += 1
    usados.add(nombre_archivo_seguro(candidato).lower())
    return candidato


def _entero_positivo(valor, campo):
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        raise PlanError(t("err_field_int", field=campo))
    if numero < 1:
        raise PlanError(t("err_field_positive", field=campo))
    return numero


def _normalizar(texto, mayusculas):
    """Unifica espacios y saltos de línea para que una frase se encuentre aunque esté partida."""
    texto = " ".join((texto or "").split())
    return texto if mayusculas else texto.casefold()


def paginas_con_texto(textos_pagina, buscado, mayusculas=False):
    """Índices (0-based) de las páginas cuyo texto contiene lo buscado."""
    aguja = _normalizar(buscado, mayusculas)
    if not aguja:
        return []
    return [i for i, texto in enumerate(textos_pagina) if aguja in _normalizar(texto, mayusculas)]


def linea_con_texto(texto_pagina, buscado, mayusculas=False):
    """Primera línea de la página que contiene lo buscado (para nombrar archivos)."""
    aguja = _normalizar(buscado, mayusculas)
    for linea in (texto_pagina or "").splitlines():
        if aguja in _normalizar(linea, mayusculas):
            return " ".join(linea.split())[:80]
    return None


def build_plan(spec, total_paginas, tamanos_pagina=None, textos_pagina=None):
    """
    Convierte una spec en una lista de (nombre, [páginas 0-based]).
    Para el modo "size" hace falta tamanos_pagina (bytes estimados de cada página)
    y para el modo "keyword", textos_pagina (texto de cada página).
    """
    modo = spec.get("mode")
    if total_paginas < 1:
        raise PlanError(t("err_no_pages"))

    if modo == "chapters":
        capitulos = spec.get("chapters") or []
        if not capitulos:
            raise PlanError(t("err_no_chapters"))
        plan, usados = [], {}
        for nombre, inicio, fin in capitulos:
            nombre = str(nombre).strip()
            if not nombre:
                raise PlanError(t("err_chapter_no_name"))
            try:
                inicio, fin = int(inicio), int(fin)
            except (TypeError, ValueError):
                raise PlanError(t("err_chapter_pages_int", name=nombre))
            if inicio < 1 or inicio > fin or fin > total_paginas:
                raise PlanError(t("err_chapter_range", name=nombre, start=inicio, end=fin, total=total_paginas))
            archivo = nombre_archivo_seguro(nombre).lower()
            if archivo in usados:
                raise PlanError(t("err_duplicate_names", a=nombre, b=usados[archivo]))
            usados[archivo] = nombre
            plan.append((nombre, list(range(inicio - 1, fin))))
        return plan

    base = str(spec.get("name") or "").strip() or t("default_part")

    if modo == "every":
        n = _entero_positivo(spec.get("n"), t("every_pages_label"))
        plan = []
        for i, inicio in enumerate(range(0, total_paginas, n), start=1):
            plan.append((f"{base} {i}", list(range(inicio, min(inicio + n, total_paginas)))))
        return plan

    if modo == "ranges":
        rangos = parse_ranges(spec.get("text", ""), total_paginas)
        if spec.get("single_file"):
            paginas = [p for inicio, fin in rangos for p in range(inicio - 1, fin)]
            return [(base, paginas)]
        plan, usados = [], set()
        for inicio, fin in rangos:
            etiqueta = f"{base} {inicio}" if inicio == fin else f"{base} {inicio}-{fin}"
            plan.append((_nombre_unico(etiqueta, usados), list(range(inicio - 1, fin))))
        return plan

    if modo == "size":
        try:
            max_mb = float(str(spec.get("max_mb")).replace(",", "."))
        except (TypeError, ValueError):
            raise PlanError(t("err_size_number"))
        if max_mb <= 0:
            raise PlanError(t("err_size_positive"))
        if tamanos_pagina is None:
            raise PlanError(t("err_size_calc"))
        limite = max_mb * 1024 * 1024
        plan, actual, acumulado = [], [], 0
        for pagina, tamano in enumerate(tamanos_pagina):
            # Una página más grande que el límite queda sola en su propio archivo
            if actual and acumulado + tamano > limite:
                plan.append(actual)
                actual, acumulado = [], 0
            actual.append(pagina)
            acumulado += tamano
        if actual:
            plan.append(actual)
        return [(f"{base} {i}", paginas) for i, paginas in enumerate(plan, start=1)]

    if modo == "keyword":
        buscado = str(spec.get("text") or "").strip()
        if not buscado:
            raise PlanError(t("err_keyword_empty"))
        if textos_pagina is None:
            raise PlanError(t("err_keyword_no_text"))
        mayusculas = bool(spec.get("case_sensitive"))
        inicios = paginas_con_texto(textos_pagina, buscado, mayusculas)
        if not inicios:
            raise PlanError(t("err_keyword_not_found", text=buscado))

        cortes = list(inicios)
        if spec.get("include_before", True) and cortes[0] > 0:
            cortes.insert(0, 0)
        plan, usados = [], set()
        for i, inicio in enumerate(cortes):
            fin = cortes[i + 1] if i + 1 < len(cortes) else total_paginas
            if inicio not in inicios:
                nombre = t("keyword_before_name", base=base)
            else:
                nombre = None
                if spec.get("name_from_match"):
                    nombre = linea_con_texto(textos_pagina[inicio], buscado, mayusculas)
                nombre = nombre or f"{base} {len(plan) + 1}"
            plan.append((_nombre_unico(nombre, usados), list(range(inicio, fin))))
        return plan

    raise PlanError(t("err_unknown_mode"))


# ----------------------------------------------------
# Lectura / escritura
# ----------------------------------------------------
def abrir_lector(ruta, password=None):
    lector = PdfReader(ruta)
    if lector.is_encrypted:
        try:
            ok = lector.decrypt(password or "")
        except Exception as e:  # p. ej. falta la librería de cifrado AES
            raise PlanError(t("err_decrypt", error=e))
        if not ok:
            raise PasswordError(t("err_password_required") if not password else t("err_password_wrong"))
    return lector


def extraer_textos(lector, cancel=None):
    """Texto de cada página (para el modo por palabra clave en procesos sin interfaz)."""
    textos = []
    for pagina in lector.pages:
        if cancel is not None and cancel.is_set():
            return None
        try:
            textos.append(pagina.extract_text() or "")
        except Exception:
            textos.append("")
    return textos


def estimar_tamanos_pagina(lector, cancel=None):
    """Tamaño aproximado (bytes) de cada página escribiéndola sola en memoria."""
    tamanos = []
    for pagina in lector.pages:
        if cancel is not None and cancel.is_set():
            return None
        escritor = PdfWriter()
        escritor.add_page(pagina)
        buffer = io.BytesIO()
        escritor.write(buffer)
        tamanos.append(buffer.tell())
    return tamanos


def leer_marcadores(lector):
    """Aplana el índice del PDF a una lista de (nivel, título, página 0-based)."""
    resultado = []

    def recorrer(items, nivel):
        for item in items:
            if isinstance(item, list):
                recorrer(item, nivel + 1)
                continue
            try:
                pagina = lector.get_destination_page_number(item)
            except Exception:
                continue
            if pagina is not None and pagina >= 0:
                resultado.append((nivel, str(item.title), pagina))

    try:
        recorrer(lector.outline, 1)
    except Exception:
        pass
    return resultado


def copiar_marcadores(escritor, marcadores, mapa_paginas):
    """Copia al escritor los marcadores cuyas páginas están en el archivo nuevo."""
    pila = []  # (nivel, objeto del marcador o None si su página no está en este archivo)
    for nivel, titulo, pagina in marcadores:
        while pila and pila[-1][0] >= nivel:
            pila.pop()
        padre = pila[-1][1] if pila else None
        if pagina in mapa_paginas:
            obj = escritor.add_outline_item(titulo, mapa_paginas[pagina], parent=padre)
        else:
            obj = None
        pila.append((nivel, obj))


def _comprimir(escritor):
    for pagina in escritor.pages:
        pagina.compress_content_streams()
    escritor.compress_identical_objects()  # elimina objetos duplicados y sin referencias


def split_pdf(ruta_pdf, spec, carpeta_salida, opciones=None, log=None, cancel=None,
              rotaciones=None, excluidas=None, password=None, textos_pagina=None):
    """
    Divide un PDF según la spec. Devuelve (archivos_generados, errores, cancelado).

    opciones: {"numbering": bool, "bookmarks": bool, "compress": bool}
    rotaciones: {página 0-based: grados extra}; excluidas: páginas 0-based a omitir.
    textos_pagina: texto ya extraído de cada página (modo "keyword"); si falta se extrae acá.
    Los archivos generados se guardan sin contraseña.
    """
    opciones = opciones or {}
    rotaciones = rotaciones or {}
    excluidas = set(excluidas or ())
    errores = []
    generados = 0

    def informar(mensaje, es_error=False, progreso=None):
        if es_error:
            errores.append(mensaje)
        if log:
            log(mensaje, es_error, progreso)

    def cancelado():
        return cancel is not None and cancel.is_set()

    if not os.path.exists(ruta_pdf):
        informar(t("log_source_missing"), True)
        return generados, errores, False

    informar(t("log_reading"))
    try:
        lector = abrir_lector(ruta_pdf, password)
        total = len(lector.pages)
        tamanos = None
        if spec.get("mode") == "size":
            informar(t("log_sizes"))
            tamanos = estimar_tamanos_pagina(lector, cancel)
            if tamanos is None:
                return generados, errores, True
            if excluidas:
                tamanos = [0 if i in excluidas else t for i, t in enumerate(tamanos)]
        if spec.get("mode") == "keyword" and textos_pagina is None:
            informar(t("log_searching"))
            textos_pagina = extraer_textos(lector, cancel)
            if textos_pagina is None:
                return generados, errores, True
        plan = build_plan(spec, total, tamanos, textos_pagina)
    except PlanError as e:
        informar(str(e), True)
        return generados, errores, False
    except Exception as e:
        informar(t("err_read_pdf", error=e), True)
        return generados, errores, False

    try:
        os.makedirs(carpeta_salida, exist_ok=True)
    except OSError as e:
        informar(t("err_create_folder", error=e), True)
        return generados, errores, False

    marcadores = leer_marcadores(lector) if opciones.get("bookmarks") else []
    nombres = nombres_de_salida(plan, opciones.get("numbering"))

    for idx, ((nombre, paginas), archivo) in enumerate(zip(plan, nombres)):
        if cancelado():
            informar(t("log_cancelled"))
            return generados, errores, True

        progreso = (idx + 1) / len(plan)
        paginas = [p for p in paginas if p not in excluidas]
        if not paginas:
            informar(t("err_empty_excluded", name=nombre), True, progreso)
            continue

        informar(t("log_creating", file=archivo))
        try:
            escritor = PdfWriter()
            mapa = {}
            for nuevo_idx, pagina in enumerate(paginas):
                pagina_nueva = escritor.add_page(lector.pages[pagina])
                if rotaciones.get(pagina):
                    pagina_nueva.rotate(rotaciones[pagina])
                mapa.setdefault(pagina, nuevo_idx)

            escritor.add_metadata({"/Title": nombre, "/Producer": APP_NAME})
            if marcadores:
                copiar_marcadores(escritor, marcadores, mapa)
            if opciones.get("compress"):
                _comprimir(escritor)

            with open(os.path.join(carpeta_salida, archivo), "wb") as salida:
                escritor.write(salida)
            generados += 1
            informar(t("log_saved", file=archivo), progreso=progreso)
        except Exception as e:
            informar(t("err_save_file", file=archivo, error=e), True, progreso)

    informar(t("log_done"), progreso=1.0)
    return generados, errores, False


def batch_split(rutas, spec, carpeta_raiz, opciones=None, log=None, cancel=None, passwords=None):
    """
    Aplica la misma spec a varios PDFs. Cada uno va a su propia carpeta:
    <carpeta_raiz>/<nombre>_dividido (o _split en inglés), o junto al PDF si carpeta_raiz es None.
    passwords: {ruta: contraseña} para los PDFs protegidos.
    Devuelve (archivos_generados, errores, cancelado, carpetas_creadas).
    """
    passwords = passwords or {}
    total_generados, errores, carpetas = 0, [], []
    for i, ruta in enumerate(rutas):
        if cancel is not None and cancel.is_set():
            return total_generados, errores, True, carpetas

        base = os.path.splitext(os.path.basename(ruta))[0]
        destino = os.path.join(carpeta_raiz or os.path.dirname(ruta), f"{base}_{t('suffix_split')}")

        def log_archivo(mensaje, es_error=False, progreso=None, i=i, base=base):
            if log:
                total = None if progreso is None else (i + progreso) / len(rutas)
                log(f"[{i + 1}/{len(rutas)}] {base}: {mensaje}", es_error, total)

        generados, errores_archivo, fue_cancelado = split_pdf(ruta, spec, destino, opciones, log_archivo, cancel,
                                                              password=passwords.get(ruta))
        total_generados += generados
        errores.extend(f"{base}: {e}" for e in errores_archivo)
        if generados:
            carpetas.append(destino)
        if fue_cancelado:
            return total_generados, errores, True, carpetas
    return total_generados, errores, False, carpetas


def merge_pdfs(rutas, ruta_salida, opciones=None, log=None, cancel=None, passwords=None):
    """Une varios PDFs en uno. Devuelve (ok, errores, cancelado)."""
    opciones = opciones or {}
    passwords = passwords or {}
    errores = []
    escritor = PdfWriter()
    for i, ruta in enumerate(rutas):
        if cancel is not None and cancel.is_set():
            return False, errores, True
        nombre = os.path.splitext(os.path.basename(ruta))[0]
        if log:
            log(t("log_adding", file=os.path.basename(ruta)), False, i / len(rutas))
        try:
            lector = abrir_lector(ruta, passwords.get(ruta))
            escritor.append(lector, outline_item=nombre if opciones.get("bookmark_per_file") else None)
        except Exception as e:
            errores.append(f"{os.path.basename(ruta)}: {e}")
            if log:
                log(t("err_add_file", file=os.path.basename(ruta), error=e), True, None)

    if not escritor.pages:
        return False, errores or [t("err_merge_none")], False

    try:
        if log:
            log(t("log_saving_merged"), False, 0.95)
        if opciones.get("compress"):
            _comprimir(escritor)
        escritor.add_metadata({"/Producer": APP_NAME})
        with open(ruta_salida, "wb") as salida:
            escritor.write(salida)
    except Exception as e:
        return False, errores + [t("err_save_merged", error=e)], False

    if log:
        log(t("log_ready"), False, 1.0)
    return True, errores, False


def capitulos_desde_indice(toc, total_paginas):
    """
    Convierte el índice de PyMuPDF (doc.get_toc()) en una lista de (nombre, inicio, fin).
    Usa el nivel más alto del índice; si ese nivel tiene una sola entrada (ej. el título
    del libro) baja al siguiente nivel.
    """
    entradas = [(nivel, titulo.strip(), pagina) for nivel, titulo, pagina, *_ in toc
                if titulo.strip() and 1 <= pagina <= total_paginas]
    if not entradas:
        return []

    niveles = sorted({nivel for nivel, _, _ in entradas})
    nivel_elegido = niveles[0]
    for nivel in niveles:
        if sum(1 for n, _, _ in entradas if n == nivel) > 1:
            nivel_elegido = nivel
            break

    # Ordenar por página y descartar entradas que empiezan en la misma página
    capitulos = []
    for _, titulo, pagina in sorted((e for e in entradas if e[0] == nivel_elegido), key=lambda e: e[2]):
        if capitulos and capitulos[-1][1] == pagina:
            continue
        capitulos.append((titulo, pagina))

    resultado, usados = [], set()
    for i, (titulo, inicio) in enumerate(capitulos):
        fin = capitulos[i + 1][1] - 1 if i + 1 < len(capitulos) else total_paginas
        resultado.append((_nombre_unico(titulo, usados), inicio, fin))
    return resultado


def describir_spec(spec):
    """Descripción corta de una spec para mostrar al usuario."""
    modo = spec.get("mode")
    if modo == "chapters":
        n = len(spec.get("chapters") or [])
        return t("spec_chapters", n=n)
    if modo == "every":
        return t("spec_every", n=spec.get("n"))
    if modo == "ranges":
        extra = t("spec_ranges_single") if spec.get("single_file") else ""
        return t("spec_ranges", text=spec.get("text", "").strip()) + extra
    if modo == "size":
        return t("spec_size", mb=spec.get("max_mb"))
    if modo == "keyword":
        return t("spec_keyword", text=spec.get("text", "").strip())
    return t("spec_unknown")
