"""
Graba las capturas y los videos de demostración para la web.

    python tools/record_demos.py                      -> ../shinobi-web/public/media
    python tools/record_demos.py --out <carpeta> --lang es

- Captura solo la ventana de la app con PrintWindow (aunque haya otras ventanas encima):
  nunca graba el resto de la pantalla.
- Genera PDFs de ejemplo realistas (un libro con capítulos y facturas) en español e inglés.
- Monta una unidad temporal con `subst` para que la app muestre rutas neutras (S:\\Documentos\\...)
  en lugar de la carpeta del usuario.
- Dibuja un cursor animado con efecto de clic sobre los videos.

Requiere: pip install imageio-ffmpeg
"""
import argparse
import ctypes
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

ESCALA = 1.5                 # Escalado de la app: 1280x800 lógicos -> 1920x1200 píxeles
TAMANO_LOGICO = (1280, 800)
FPS = 30
VELOCIDAD = 1.45          # Los videos se aceleran al postprocesar
TRANSICION_ZOOM = 0.75    # Segundos (de grabación) que tarda en acercarse o alejarse la cámara

TEXTOS = {
    "es": {
        "carpeta": "Documentos",
        "libro": "Guía de fotografía.pdf",
        "libro_titulo": "Guía práctica de fotografía",
        "libro_sub": "De la primera foto a tu propio estilo",
        "autor": "Lucía Ferrer",
        "capitulos": ["Introducción", "La luz", "Composición", "El color", "Edición", "Conclusión"],
        "capitulo": "Capítulo",
        "parrafos": [
            "La fotografía es, ante todo, el arte de observar. Antes de tocar la cámara conviene mirar la escena, entender de dónde viene la luz y qué historia queremos contar.",
            "Cada decisión técnica tiene un efecto visual. La apertura controla la profundidad de campo, la velocidad congela o desenfoca el movimiento y la sensibilidad define cuánto ruido aceptamos.",
            "La composición ordena los elementos del cuadro. La regla de los tercios, las líneas guía y el espacio negativo ayudan a dirigir la mirada de quien observa.",
            "El color transmite emociones. Los tonos cálidos acercan y dan energía; los fríos generan calma y distancia. Una paleta limitada suele ser más poderosa.",
        ],
        "facturas": "Facturas de marzo.pdf",
        "resumen": "Resumen de facturación · Marzo",
        "factura": "Factura N° 0001-0000{n}",
        "empresa": "Estudio Nimbus",
        "cliente": "Cliente",
        "clientes": ["Café del Puerto", "Librería Andes", "Taller Norte", "Hotel Patagonia"],
        "items": ["Diseño de identidad visual", "Sesión de fotos de producto", "Impresión de catálogos", "Mantenimiento web mensual", "Edición de video corto"],
        "detalle": "Detalle", "cant": "Cant.", "precio": "Precio", "total": "Total",
        "continua": "Continúa en la página siguiente",
        "busqueda": "composición",
        "clave": "Factura N",
        "unir": ["Contrato firmado.pdf", "Anexo técnico.pdf", "Presupuesto 2026.pdf"],
    },
    "en": {
        "carpeta": "Documents",
        "libro": "Photography Guide.pdf",
        "libro_titulo": "A Practical Guide to Photography",
        "libro_sub": "From your first shot to your own style",
        "autor": "Lucy Ferrer",
        "capitulos": ["Introduction", "Light", "Composition", "Color", "Editing", "Conclusion"],
        "capitulo": "Chapter",
        "parrafos": [
            "Photography is, above all, the art of seeing. Before touching the camera, look at the scene, understand where the light comes from and what story you want to tell.",
            "Every technical choice has a visual effect. Aperture controls depth of field, shutter speed freezes or blurs motion and ISO defines how much noise you accept.",
            "Composition organizes the elements in the frame. The rule of thirds, leading lines and negative space help guide the viewer's eye.",
            "Color conveys emotion. Warm tones feel close and energetic; cool tones bring calm and distance. A limited palette is often more powerful.",
        ],
        "facturas": "March invoices.pdf",
        "resumen": "Billing summary · March",
        "factura": "Invoice No. 0001-0000{n}",
        "empresa": "Nimbus Studio",
        "cliente": "Client",
        "clientes": ["Harbor Café", "Andes Books", "North Workshop", "Patagonia Hotel"],
        "items": ["Brand identity design", "Product photo shoot", "Catalog printing", "Monthly website maintenance", "Short video editing"],
        "detalle": "Description", "cant": "Qty", "precio": "Price", "total": "Total",
        "continua": "Continued on next page",
        "busqueda": "composition",
        "clave": "Invoice No",
        "unir": ["Signed contract.pdf", "Technical annex.pdf", "Budget 2026.pdf"],
    },
}

AZUL = (0.2, 0.227, 0.984)
MARINO = (0.027, 0.055, 0.149)
FOTOS = [(0.96, 0.62, 0.33), (0.36, 0.55, 0.85), (0.42, 0.7, 0.55), (0.85, 0.45, 0.55), (0.55, 0.45, 0.85)]


# ----------------------------------------------------
# PDFs de ejemplo
# ----------------------------------------------------
def crear_libro(ruta, tx):
    import fitz
    doc = fitz.open()
    W, H = 595, 842

    portada = doc.new_page(width=W, height=H)
    portada.draw_rect(portada.rect, color=None, fill=MARINO)
    portada.draw_rect(fitz.Rect(0, 520, W, 842), color=None, fill=AZUL)
    portada.draw_circle(fitz.Point(430, 300), 110, color=None, fill=(0.31, 0.33, 1.0))
    portada.draw_circle(fitz.Point(430, 300), 60, color=None, fill=MARINO)
    portada.insert_textbox(fitz.Rect(56, 120, 380, 300), tx["libro_titulo"], fontsize=34, fontname="hebo", color=(1, 1, 1))
    portada.insert_textbox(fitz.Rect(56, 300, 380, 360), tx["libro_sub"], fontsize=14, fontname="helv", color=(0.75, 0.78, 0.95))
    portada.insert_text((56, 780), tx["autor"], fontsize=13, fontname="hebo", color=(1, 1, 1))
    toc = []

    pagina_num = 2
    for i, titulo in enumerate(tx["capitulos"]):
        apertura = doc.new_page(width=W, height=H)
        toc.append([1, titulo, pagina_num])
        apertura.draw_rect(fitz.Rect(0, 0, W, 300), color=None, fill=FOTOS[i % len(FOTOS)])
        apertura.insert_text((56, 380), f"{tx['capitulo']} {i}" if 0 < i < len(tx["capitulos"]) - 1 else "", fontsize=14,
                             fontname="helv", color=AZUL)
        apertura.insert_textbox(fitz.Rect(56, 395, 540, 480), titulo, fontsize=36, fontname="hebo", color=MARINO)
        apertura.insert_textbox(fitz.Rect(56, 500, 540, 700), " ".join(tx["parrafos"][i % 4:i % 4 + 2]), fontsize=12,
                                fontname="helv", color=(0.25, 0.27, 0.35), lineheight=1.5)
        pagina_num += 1
        for j in range(3):
            pagina = doc.new_page(width=W, height=H)
            pagina.insert_text((56, 60), f"{titulo}", fontsize=9, fontname="helv", color=(0.55, 0.57, 0.65))
            pagina.draw_line(fitz.Point(56, 68), fitz.Point(539, 68), color=(0.85, 0.86, 0.9), width=0.6)
            y = 100
            if j == 1:
                pagina.draw_rect(fitz.Rect(56, y, 539, y + 230), color=None, fill=FOTOS[(i + j) % len(FOTOS)])
                y += 255
            for k in range(3):
                texto = tx["parrafos"][(i + j + k) % 4]
                caja = fitz.Rect(56, y, 539, y + 120)
                pagina.insert_textbox(caja, texto, fontsize=11.5, fontname="helv", color=(0.18, 0.2, 0.28), lineheight=1.55)
                y += 115
            pagina.insert_text((W / 2 - 6, 810), str(pagina_num), fontsize=9, fontname="helv", color=(0.55, 0.57, 0.65))
            pagina_num += 1
    doc.set_toc(toc)
    doc.save(ruta)


def crear_facturas(ruta, tx):
    import fitz
    doc = fitz.open()
    W, H = 595, 842
    resumen = doc.new_page(width=W, height=H)
    resumen.draw_rect(fitz.Rect(0, 0, W, 140), color=None, fill=MARINO)
    resumen.insert_text((56, 85), tx["empresa"], fontsize=24, fontname="hebo", color=(1, 1, 1))
    resumen.insert_text((56, 200), tx["resumen"], fontsize=18, fontname="hebo", color=MARINO)
    for n, cliente in enumerate(tx["clientes"]):
        # Sin la palabra clave: si no, la página de resumen también contaría como factura en la demo
        resumen.insert_text((56, 250 + n * 30), f"0001-0000{1230 + n}  ·  {cliente}", fontsize=11,
                            fontname="helv", color=(0.25, 0.27, 0.35))

    paginas_por_factura = [2, 1, 2, 1]
    for n, (cliente, cantidad_paginas) in enumerate(zip(tx["clientes"], paginas_por_factura)):
        for p in range(cantidad_paginas):
            pagina = doc.new_page(width=W, height=H)
            pagina.draw_rect(fitz.Rect(0, 0, W, 8), color=None, fill=AZUL)
            pagina.insert_text((56, 70), tx["empresa"], fontsize=16, fontname="hebo", color=MARINO)
            if p == 0:
                pagina.insert_text((56, 130), tx["factura"].format(n=1230 + n), fontsize=20, fontname="hebo", color=AZUL)
                pagina.insert_text((56, 165), f"{tx['cliente']}: {cliente}", fontsize=11, fontname="helv", color=(0.25, 0.27, 0.35))
                y = 220
            else:
                y = 120
            pagina.draw_rect(fitz.Rect(56, y, 539, y + 26), color=None, fill=(0.94, 0.95, 0.99))
            for x, encabezado in ((66, tx["detalle"]), (380, tx["cant"]), (450, tx["precio"])):
                pagina.insert_text((x, y + 17), encabezado, fontsize=10, fontname="hebo", color=MARINO)
            y += 46
            for k in range(5 if p == 0 else 3):
                item = tx["items"][(n + k + p) % len(tx["items"])]
                pagina.insert_text((66, y), item, fontsize=10.5, fontname="helv", color=(0.18, 0.2, 0.28))
                pagina.insert_text((390, y), str((k % 3) + 1), fontsize=10.5, fontname="helv", color=(0.18, 0.2, 0.28))
                pagina.insert_text((450, y), f"$ {(k + 2) * 18_500 + n * 3_200:,}".replace(",", "."), fontsize=10.5,
                                   fontname="helv", color=(0.18, 0.2, 0.28))
                pagina.draw_line(fitz.Point(56, y + 12), fitz.Point(539, y + 12), color=(0.9, 0.91, 0.94), width=0.5)
                y += 34
            if p == cantidad_paginas - 1:
                pagina.insert_text((380, y + 30), tx["total"], fontsize=13, fontname="hebo", color=MARINO)
                pagina.insert_text((450, y + 30), f"$ {184_000 + n * 21_700:,}".replace(",", "."), fontsize=13,
                                   fontname="hebo", color=AZUL)
            else:
                pagina.insert_text((56, 790), tx["continua"], fontsize=9, fontname="heit", color=(0.55, 0.57, 0.65))
    doc.save(ruta)


def crear_simple(ruta, titulo, color, paginas=3):
    import fitz
    doc = fitz.open()
    for i in range(paginas):
        pagina = doc.new_page(width=595, height=842)
        pagina.draw_rect(fitz.Rect(0, 0, 595, 120), color=None, fill=color)
        pagina.insert_text((56, 75), titulo, fontsize=22, fontname="hebo", color=(1, 1, 1))
        for k in range(6):
            pagina.draw_rect(fitz.Rect(56, 170 + k * 70, 539 - (k % 3) * 60, 180 + k * 70), color=None, fill=(0.88, 0.89, 0.93))
    doc.save(ruta)


# ----------------------------------------------------
# Unidad temporal con subst (rutas neutras en la interfaz)
# ----------------------------------------------------
def montar_unidad(carpeta):
    usadas = {d[0] for d in os.popen("subst").read().split() if len(d) == 3 and d[1:] == ":\\"}
    disponibles = [l for l in "STUVWXYZ" if not os.path.exists(f"{l}:\\") and l not in usadas]
    if not disponibles:
        return None
    letra = disponibles[0]
    subprocess.run(["subst", f"{letra}:", carpeta], check=True)
    return f"{letra}:\\"


def desmontar_unidad(raiz):
    if raiz:
        subprocess.run(["subst", raiz[:2], "/D"], capture_output=True)


# ----------------------------------------------------
# Captura de la ventana y grabación
# ----------------------------------------------------
user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32


class _BIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def capturar_ventana(app):
    """Imagen del área de cliente de la ventana (sin barra de título), aunque esté tapada."""
    from PIL import Image
    # Terminar de dibujar los cambios pendientes: si no, la captura sale a medio redibujar
    app.update_idletasks()
    hwnd = int(app.wm_frame(), 16)
    wr = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wr))
    w, h = wr.right - wr.left, wr.bottom - wr.top
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    user32.PrintWindow(hwnd, mem, 2)  # PW_RENDERFULLCONTENT
    bih = _BIH(ctypes.sizeof(_BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buffer = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buffer, ctypes.byref(bih), 0)
    img = Image.frombuffer("RGBA", (w, h), buffer, "raw", "BGRA", 0, 1).convert("RGB")
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)
    origen = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origen))
    cliente = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(cliente))
    x0, y0 = origen.x - wr.left, origen.y - wr.top
    return img.crop((x0, y0, x0 + cliente.right, y0 + cliente.bottom))


def _sprite_cursor(escala=1.5):
    """Flecha de cursor blanca con borde oscuro (estilo macOS) en alta resolución."""
    from PIL import Image, ImageDraw
    s = 4  # Sobremuestreo para bordes suaves
    puntos = [(0, 0), (0, 17), (4.5, 13), (7.5, 20), (10, 19), (7, 12), (12.5, 12)]
    tam = int(26 * escala * s)
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    p = [(2 * s + x * escala * s, 2 * s + y * escala * s) for x, y in puntos]
    sombra = [(x + 1.5 * s, y + 2 * s) for x, y in p]
    d.polygon(sombra, fill=(0, 0, 0, 70))
    d.polygon(p, fill=(255, 255, 255, 255), outline=(10, 12, 25, 255), width=int(1.6 * s))
    return img.resize((tam // s, tam // s), Image.LANCZOS)


def _suavizar(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


class Grabador:
    """
    Graba la ventana a FPS fijos y compone un cursor animado encima.
    Al terminar hace una segunda pasada que agrega zoom con seguimiento del cursor (estilo
    screen.studio) y acelera el video.
    """

    def __init__(self, app, ruta_mp4):
        import imageio_ffmpeg
        self.app = app
        self.ruta = ruta_mp4
        self.ruta_cruda = ruta_mp4 + ".crudo.mp4"
        self.sprite = _sprite_cursor(ESCALA)
        self.cursor = None          # Posición actual (x, y) o None si no se muestra
        self.mov = None             # (inicio, fin, t0, duración)
        self.movs = []              # Historial de movimientos (para la cámara)
        self.camara = []            # (tiempo, nivel de zoom, foco o None = seguir al cursor)
        self.clics = []             # Tiempos de clic (para la onda)
        self.t0 = None
        self.escritos = 0
        self.activo = False
        self.tam = None
        self.escritor = None
        self._imageio_ffmpeg = imageio_ffmpeg

    def _pos_cursor(self, t):
        if self.mov:
            ini, fin, t0, dur = self.mov
            k = _suavizar((t - t0) / dur)
            return ini[0] + (fin[0] - ini[0]) * k, ini[1] + (fin[1] - ini[1]) * k
        return self.cursor

    def _pos_en(self, t):
        """Posición del cursor en un instante pasado (usa el historial de movimientos)."""
        pos = None
        for ini, fin, t0, dur in self.movs:
            if t0 > t:
                break
            k = _suavizar((t - t0) / dur)
            pos = (ini[0] + (fin[0] - ini[0]) * k, ini[1] + (fin[1] - ini[1]) * k)
        return pos

    def mover(self, destino, duracion=0.7):
        ahora = time.perf_counter()
        inicio = self._pos_cursor(ahora) or (destino[0] + 260, destino[1] + 180)
        self.mov = (inicio, destino, ahora, duracion)
        self.movs.append(self.mov)
        self.cursor = destino

    def zoom(self, nivel, foco=None):
        self.camara.append((time.perf_counter(), nivel, foco))

    def clic(self):
        self.clics.append(time.perf_counter())

    def iniciar(self):
        primera = capturar_ventana(self.app)
        self.tam = primera.size
        # Primera pasada rápida y casi sin pérdida; la compresión final se hace al postprocesar
        self.escritor = self._imageio_ffmpeg.write_frames(
            self.ruta_cruda, self.tam, fps=FPS, codec="libx264", pix_fmt_out="yuv420p", macro_block_size=8,
            output_params=["-crf", "14", "-preset", "veryfast"])
        self.escritor.send(None)
        self.t0 = time.perf_counter()
        self.activo = True
        self._tick()

    def _componer(self, img, t):
        from PIL import ImageDraw
        pos = self._pos_cursor(t)
        if pos is None:
            return img
        img = img.copy()
        for tc in self.clics:
            edad = t - tc
            if 0 <= edad < 0.45:
                r = 10 + 38 * _suavizar(edad / 0.45)
                alfa = int(150 * (1 - edad / 0.45))
                capa = img.convert("RGBA")
                d = ImageDraw.Draw(capa, "RGBA")
                d.ellipse((pos[0] - r, pos[1] - r, pos[0] + r, pos[1] + r), outline=(120, 125, 255, alfa), width=4,
                          fill=(80, 85, 255, alfa // 4))
                img = capa.convert("RGB")
        img.paste(self.sprite, (int(pos[0] - 3), int(pos[1] - 3)), self.sprite)
        return img

    def _tick(self):
        if not self.activo:
            return
        inicio = time.perf_counter()
        try:
            cuadro = capturar_ventana(self.app)
        except Exception:
            cuadro = None
        if cuadro is not None and cuadro.size == self.tam:
            debidos = int((inicio - self.t0) * FPS) + 1
            while self.escritos < debidos:
                t = self.t0 + self.escritos / FPS
                self.escritor.send(self._componer(cuadro, t).tobytes())
                self.escritos += 1
        espera = max(1, int(1000 / FPS - (time.perf_counter() - inicio) * 1000))
        self.app.after(espera, self._tick)

    def terminar(self):
        self.activo = False
        if self.escritor is not None:
            self.escritor.close()
            self._postprocesar()

    # ------------------------------------------------
    # Segunda pasada: zoom con seguimiento y aceleración
    # ------------------------------------------------
    def _segmentos_zoom(self):
        """[(t_inicio, zoom_inicial, zoom_final, foco)] encadenados: cada uno arranca donde quedó el anterior."""
        segmentos, actual = [], 1.0
        for tk, nivel, foco in self.camara:
            if segmentos:
                ts, z0, z1, _ = segmentos[-1]
                actual = z0 + (z1 - z0) * _suavizar((tk - ts) / TRANSICION_ZOOM)
            segmentos.append((tk, actual, nivel, foco))
        return segmentos

    def _postprocesar(self):
        from PIL import Image
        W, H = self.tam
        segmentos = self._segmentos_zoom()
        lector = self._imageio_ffmpeg.read_frames(self.ruta_cruda)
        meta = next(lector)
        total_entrada = int(meta["duration"] * FPS)
        escritor = self._imageio_ffmpeg.write_frames(
            self.ruta, self.tam, fps=FPS, codec="libx264", pix_fmt_out="yuv420p", macro_block_size=8,
            output_params=["-crf", "22", "-preset", "slow", "-movflags", "+faststart"])
        escritor.send(None)

        centro = (W / 2, H / 2)
        indice_entrada, cuadro = -1, None
        j = 0
        try:
            while True:
                t_rel = j / FPS * VELOCIDAD
                objetivo = int(t_rel * FPS)
                if objetivo >= total_entrada:
                    break
                while indice_entrada < objetivo:
                    try:
                        cuadro = next(lector)
                    except StopIteration:
                        cuadro = None
                        break
                    indice_entrada += 1
                if cuadro is None:
                    break
                t = self.t0 + t_rel

                # Nivel de zoom y punto de interés en este instante
                nivel, foco = 1.0, None
                for ts, z0, z1, f in segmentos:
                    if ts > t:
                        break
                    nivel, foco = z0 + (z1 - z0) * _suavizar((t - ts) / TRANSICION_ZOOM), f
                destino = foco or self._pos_en(t) or (W / 2, H / 2)
                # La cámara sigue al punto de interés con suavidad (sin saltos)
                centro = (centro[0] + (destino[0] - centro[0]) * 0.16, centro[1] + (destino[1] - centro[1]) * 0.16)

                imagen = Image.frombytes("RGB", (W, H), cuadro)
                if nivel > 1.001:
                    mw, mh = W / nivel / 2, H / nivel / 2
                    cx = min(max(centro[0], mw), W - mw)
                    cy = min(max(centro[1], mh), H - mh)
                    imagen = imagen.crop((round(cx - mw), round(cy - mh), round(cx + mw), round(cy + mh)))
                    imagen = imagen.resize((W, H), Image.BICUBIC)
                escritor.send(imagen.tobytes())
                j += 1
        finally:
            escritor.close()
            lector.close()
            try:
                os.remove(self.ruta_cruda)
            except OSError:
                pass


# ----------------------------------------------------
# Guion de cada escena
# ----------------------------------------------------
class Escena:
    """Ejecuta una lista de pasos (espera_ms, acción) con after() y graba si se pide."""

    def __init__(self, app, salida, nombre, grabar=True):
        self.app = app
        self.salida = salida
        self.nombre = nombre
        self.pasos = []
        self.grabador = Grabador(app, os.path.join(salida, f"{nombre}.mp4")) if grabar else None

    def centro(self, widget, dx=0, dy=0):
        self.app.update_idletasks()
        x = widget.winfo_rootx() - self.app.winfo_rootx() + widget.winfo_width() / 2 + dx
        y = widget.winfo_rooty() - self.app.winfo_rooty() + widget.winfo_height() / 2 + dy
        return x, y

    def paso(self, espera_ms, accion=None):
        self.pasos.append((espera_ms, accion))
        return self

    def mover(self, widget_o_punto, espera_ms=750, duracion=0.65, dx=0, dy=0):
        def accion():
            if self.grabador:
                destino = widget_o_punto() if callable(widget_o_punto) else widget_o_punto
                if not isinstance(destino, tuple):
                    destino = self.centro(destino, dx, dy)
                self.grabador.mover(destino, duracion)
        return self.paso(espera_ms, accion)

    def zoom(self, nivel, foco=None, espera_ms=0):
        """Acerca (nivel > 1) o aleja (nivel = 1) la cámara; sin foco sigue al cursor."""
        def accion():
            if self.grabador:
                punto = foco() if callable(foco) else foco
                if punto is not None and not isinstance(punto, tuple):
                    punto = self.centro(punto)
                self.grabador.zoom(nivel, punto)
        return self.paso(espera_ms, accion)

    def clic(self, accion, espera_ms=450):
        def ejecutar():
            if self.grabador:
                self.grabador.clic()
            self.app.after(120, accion)
        return self.paso(espera_ms, ejecutar)

    def escribir(self, entry, texto, por_letra_ms=85, despues=None):
        for i in range(1, len(texto) + 1):
            def poner(parcial=texto[:i]):
                entry.delete(0, "end")
                entry.insert(0, parcial)
                if despues:
                    despues()
            self.paso(por_letra_ms, poner)
        return self

    def captura(self, nombre, espera_ms=200):
        def accion():
            img = capturar_ventana(self.app)
            img.save(os.path.join(self.salida, f"{nombre}.png"))
            img.convert("RGB").save(os.path.join(self.salida, f"{nombre}.webp"), quality=88, method=6)
        return self.paso(espera_ms, accion)

    def correr(self):
        listo = {"ok": False}

        def siguiente(i=0):
            if i >= len(self.pasos):
                if self.grabador:
                    self.grabador.terminar()
                listo["ok"] = True
                self.app.after(100, self.app.destroy)
                return
            espera, accion = self.pasos[i]

            def ejecutar():
                if accion:
                    accion()
                siguiente(i + 1)
            self.app.after(espera, ejecutar)

        def arrancar():
            if self.grabador:
                self.grabador.iniciar()
            siguiente()
        self.app.after(1800, arrancar)
        self.app.mainloop()
        return listo["ok"]


def nueva_app(idioma, tema, appdata, archivos=None):
    """Crea la app con una configuración limpia (sin tour ni búsqueda de actualizaciones)."""
    os.environ["APPDATA"] = appdata
    carpeta = os.path.join(appdata, "ShinobiPDF")
    shutil.rmtree(carpeta, ignore_errors=True)
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"language": idioma, "theme": tema, "onboarding_done": True, "last_version": "1.0",
                   "check_updates": False, "options": {"numbering": True, "bookmarks": True, "compress": False}}, f)
    import customtkinter as ctk
    ctk.set_window_scaling(ESCALA)
    ctk.set_widget_scaling(ESCALA)
    from shinobi.app import App
    app = App(files=archivos)
    app.geometry(f"{TAMANO_LOGICO[0]}x{TAMANO_LOGICO[1]}+0+0")
    return app


# Cada escena corre en su propio proceso: CustomTkinter no tolera crear otra ventana principal
# en el mismo proceso después de cerrar la anterior.
def escena_split(salida, idioma, docs, appdata, grabar):
    tx = TEXTOS[idioma]
    libro = os.path.join(docs, tx["libro"])
    app = nueva_app(idioma, "dark", appdata)
    sv = app.views["split"]
    e = Escena(app, salida, f"split-{idioma}", grabar)
    e.paso(900)
    e.mover(lambda: e.centro(sv.empty_state, dy=60))
    e.clic(lambda: (sv.open_pdf(libro), app._hide_toast()), 1200)
    e.mover(sv.detect_btn, 500)
    e.zoom(1.75, espera_ms=350)
    e.clic(lambda: (sv.detect_chapters(), app._hide_toast()), 500)
    e.zoom(1.35, foco=lambda: e.centro(sv.rows_frame), espera_ms=900)
    e.zoom(1.0, espera_ms=1100)
    e.mover(lambda: e.centro(sv.thumbs, dx=120), 700)
    e.zoom(1.6, espera_ms=200)
    e.clic(lambda: sv.go_to_page(10), 300)
    e.paso(700)
    e.zoom(1.0, espera_ms=200)
    e.captura(f"split-{idioma}", 400)
    e.mover(sv.execute_btn, 800)
    e.zoom(1.5, espera_ms=100)
    e.clic(lambda: sv.process(), 1400)
    e.zoom(1.0, espera_ms=1200)
    e.captura(f"split-done-{idioma}", 300)
    e.paso(1800)
    e.correr()


def escena_keyword(salida, idioma, docs, appdata, grabar):
    tx = TEXTOS[idioma]
    app = nueva_app(idioma, "dark", appdata, [os.path.join(docs, tx["facturas"])])
    sv = app.views["split"]
    e = Escena(app, salida, f"keyword-{idioma}", grabar)
    e.paso(1000, app._hide_toast)
    e.mover(lambda: e.centro(sv.mode_selector, dx=sv.mode_selector.winfo_width() * 0.4), 800)
    e.zoom(1.7, espera_ms=100)
    e.clic(lambda: sv.set_mode("keyword"), 700)
    e.mover(sv.keyword_text, 700)
    e.clic(lambda: sv.keyword_text.focus_set(), 300)
    e.escribir(sv.keyword_text, tx["clave"], despues=sv.schedule_update)
    e.zoom(1.4, foco=lambda: e.centro(sv.keyword_preview, dy=-40), espera_ms=700)
    e.zoom(1.0, espera_ms=1300)
    e.paso(1200)
    e.captura(f"keyword-{idioma}", 300)
    e.mover(sv.execute_btn, 1000)
    e.paso(1500)
    e.correr()


def escena_search(salida, idioma, docs, appdata, grabar):
    tx = TEXTOS[idioma]
    app = nueva_app(idioma, "dark", appdata, [os.path.join(docs, tx["libro"])])
    sv = app.views["split"]
    e = Escena(app, salida, f"search-{idioma}", grabar)
    e.paso(1000, app._hide_toast)
    e.mover(sv.search_btn, 800)
    e.zoom(1.7, espera_ms=100)
    e.clic(lambda: sv.toggle_search(True), 600)
    e.escribir(sv.search_entry, tx["busqueda"], 90)
    e.paso(400, sv._run_search)
    e.zoom(1.5, foco=lambda: e.centro(sv.image_container, dy=-120), espera_ms=600)
    e.paso(1400)
    e.zoom(1.0, espera_ms=300)
    e.paso(900)
    e.captura(f"search-{idioma}", 200)
    e.mover(lambda: sv.search_next_btn, 600)
    e.clic(lambda: sv.search_step(1), 1100)
    e.clic(lambda: sv.search_step(1), 1300)
    e.paso(800)
    e.correr()


def escena_merge(salida, idioma, docs, appdata, grabar):
    tx = TEXTOS[idioma]
    extras = []
    for nombre, color in zip(tx["unir"], [(0.2, 0.23, 0.98), (0.06, 0.6, 0.45), (0.9, 0.5, 0.15)]):
        ruta = os.path.join(docs, nombre)
        crear_simple(ruta, os.path.splitext(nombre)[0], color)
        extras.append(ruta)
    extras.append(os.path.join(docs, tx["facturas"]))
    app = nueva_app(idioma, "dark", appdata)
    mv = app.views["merge"]
    e = Escena(app, salida, f"merge-{idioma}", grabar)
    # Sin zoom: la lista ocupa todo el ancho y cualquier acercamiento corta las flechas de la derecha
    e.paso(600, lambda: app.show_view("merge"))
    for ruta in extras:
        e.paso(600, lambda r=ruta: mv.files.add_files([r]))
    e.paso(500)
    e.mover(lambda: e.centro(mv.files.items[-1]["frame"], dx=mv.files.items[-1]["frame"].winfo_width() / 2 - 100), 700)
    e.clic(lambda: mv.files.move(mv.files.items[-1], -1), 700)
    # El archivo subió una fila: el cursor lo acompaña antes de volver a subirlo
    e.mover(lambda: e.centro(mv.files.items[-2]["frame"], dx=mv.files.items[-2]["frame"].winfo_width() / 2 - 100), 500, 0.35)
    e.clic(lambda: mv.files.move(mv.files.items[-2], -1), 900)
    e.captura(f"merge-{idioma}", 200)
    e.mover(mv.merge_btn, 900)
    e.paso(1300)
    e.correr()


def escena_light(salida, idioma, docs, appdata, grabar):
    tx = TEXTOS[idioma]
    app = nueva_app(idioma, "light", appdata, [os.path.join(docs, tx["libro"])])
    sv = app.views["split"]
    e = Escena(app, salida, "light", grabar=False)
    e.paso(1000, lambda: (app._hide_toast(), sv.detect_chapters(), app._hide_toast()))
    e.paso(600, lambda: sv.go_to_page(6))
    e.captura(f"split-light-{idioma}", 900)
    e.paso(300, lambda: app.show_view("images"))
    e.captura(f"images-light-{idioma}", 700)
    e.correr()


def escena_batch(salida, idioma, docs, appdata, grabar):
    tx = TEXTOS[idioma]
    archivos = [os.path.join(docs, tx["libro"]), os.path.join(docs, tx["facturas"])]
    app = nueva_app(idioma, "dark", appdata)
    e = Escena(app, salida, "batch", grabar=False)
    e.paso(1000, lambda: (app.show_view("batch"), app.views["batch"].files.add_files(archivos)))
    e.captura(f"batch-{idioma}", 700)
    e.correr()


ESCENAS = {"split": escena_split, "keyword": escena_keyword, "search": escena_search,
           "merge": escena_merge, "light": escena_light, "batch": escena_batch}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(os.path.dirname(RAIZ), "shinobi-web", "public", "media"))
    parser.add_argument("--lang", choices=["es", "en", "all"], default="all")
    parser.add_argument("--only", nargs="*", choices=list(ESCENAS), help="Grabar solo estas escenas")
    parser.add_argument("--stills", action="store_true", help="Solo capturas, sin videos")
    # Uso interno: ejecutar una sola escena en este proceso
    parser.add_argument("--scene", help=argparse.SUPPRESS)
    parser.add_argument("--docs", help=argparse.SUPPRESS)
    parser.add_argument("--appdata", help=argparse.SUPPRESS)
    args = parser.parse_args()
    salida = os.path.abspath(args.out)

    if args.scene:
        ESCENAS[args.scene](salida, args.lang, args.docs, args.appdata, not args.stills)
        return

    os.makedirs(salida, exist_ok=True)
    trabajo = tempfile.mkdtemp(prefix="shinobi-demo-")
    raiz = montar_unidad(trabajo) or trabajo
    print("Documentos de ejemplo en:", raiz)
    try:
        for idioma in (["es", "en"] if args.lang == "all" else [args.lang]):
            tx = TEXTOS[idioma]
            docs = os.path.join(raiz, tx["carpeta"])
            os.makedirs(docs, exist_ok=True)
            crear_libro(os.path.join(docs, tx["libro"]), tx)
            crear_facturas(os.path.join(docs, tx["facturas"]), tx)
            for nombre in (args.only or list(ESCENAS)):
                comando = [sys.executable, os.path.abspath(__file__), "--scene", nombre, "--lang", idioma,
                           "--docs", docs, "--appdata", os.path.join(trabajo, "_appdata"), "--out", salida]
                if args.stills:
                    comando.append("--stills")
                # A veces Tk falla al cerrar la ventana con tareas pendientes: se reintenta una vez
                for intento in range(2):
                    resultado = subprocess.run(comando)
                    if resultado.returncode == 0:
                        break
                print(f"{idioma}/{nombre}:", "ok" if resultado.returncode == 0 else f"error {resultado.returncode}")
    finally:
        if raiz != trabajo:
            desmontar_unidad(raiz)
        shutil.rmtree(trabajo, ignore_errors=True)
    print("Material guardado en", salida)


if __name__ == "__main__":
    main()
