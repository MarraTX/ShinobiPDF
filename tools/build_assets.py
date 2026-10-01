"""
Genera los recursos de la marca en shinobi/assets a partir de las imágenes originales de img/.

    python tools/build_assets.py

- Limpia los bordes semitransparentes y los puntos sueltos que quedan al quitar el fondo.
- Crea variantes para modo oscuro (texto claro y contorno claro alrededor del ninja).
- Genera icon.ico con todos los tamaños que usa Windows.
"""
import os

from PIL import Image, ImageFilter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEN_LOGO = os.path.join(RAIZ, "img", "Logotipo horizontal del ninja Shinobi.pdf.png")
ORIGEN_ICONO = os.path.join(RAIZ, "img", "Ninja corta el PDF-1.png")
DESTINO = os.path.join(RAIZ, "shinobi", "assets")

COLOR_CLARO = (232, 234, 237)
# En el logo horizontal, a partir de esta columna (en el original) empieza el texto "Shinobi.pdf"
INICIO_TEXTO_LOGO = 640
# Zona del logo original donde está la estrella ninja que hace de punto en "Shinobi.pdf"
CAJA_ESTRELLA = (1540, 385, 1700, 540)


def limpiar(img):
    """Endurece la transparencia y elimina puntos sueltos alrededor de la figura."""
    img = img.convert("RGBA")
    r, g, b, a = img.split()
    a = a.point(lambda v: 0 if v < 70 else 255 if v > 200 else int((v - 70) * 255 / 130))
    # Apertura morfológica sobre la máscara: borra manchas chicas sin tocar la figura
    mascara = a.point(lambda v: 255 if v > 0 else 0)
    mascara = mascara.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MaxFilter(9))
    a = Image.composite(a, Image.new("L", a.size, 0), mascara)
    return Image.merge("RGBA", (r, g, b, a))


def recortar(img, margen=0.04):
    caja = img.getchannel("A").getbbox()
    img = img.crop(caja)
    m = int(max(img.size) * margen)
    lienzo = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
    lienzo.paste(img, (m, m))
    return lienzo


def contorno(img, grosor, color=COLOR_CLARO):
    """Agrega un contorno (estilo sticker) para que la figura se distinga sobre fondos oscuros."""
    alfa = img.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    borde = alfa.filter(ImageFilter.MaxFilter(grosor * 2 + 1)).filter(ImageFilter.GaussianBlur(1))
    fondo = Image.new("RGBA", img.size, color + (0,))
    fondo.putalpha(borde)
    fondo.alpha_composite(img)
    return fondo


def aclarar_oscuros(img, color=COLOR_CLARO, umbral=100):
    """Reemplaza el azul marino del texto por un color claro (sin tocar la estrella azul)."""
    pixeles = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = pixeles[x, y]
            if a and max(r, g, b) < umbral:
                pixeles[x, y] = color + (a,)
    return img


def extraer_estrella(logo):
    """Recorta la estrella ninja del logo quedándose solo con los píxeles azules."""
    zona = logo.crop(CAJA_ESTRELLA)
    pixeles = zona.load()
    for y in range(zona.height):
        for x in range(zona.width):
            r, g, b, a = pixeles[x, y]
            if not (b > 150 and r < 140 and g < 140):
                pixeles[x, y] = (0, 0, 0, 0)
    return recortar(zona, 0.06)


def cuadrado(img, lado):
    """Centra la imagen en un lienzo cuadrado transparente."""
    lado_lienzo = max(img.size)
    lienzo = Image.new("RGBA", (lado_lienzo, lado_lienzo), (0, 0, 0, 0))
    lienzo.paste(img, ((lado_lienzo - img.width) // 2, (lado_lienzo - img.height) // 2))
    return lienzo.resize((lado, lado), Image.LANCZOS)


def main():
    os.makedirs(DESTINO, exist_ok=True)

    # Ícono
    icono = recortar(limpiar(Image.open(ORIGEN_ICONO)))
    cuadrado(icono, 512).save(os.path.join(DESTINO, "icon.png"))
    icono_contorno = cuadrado(contorno(icono, 14), 512)
    icono_contorno.save(os.path.join(DESTINO, "icon_dark.png"))
    # El .ico usa la versión con contorno: se distingue en barras de tareas claras y oscuras
    icono_contorno.save(os.path.join(DESTINO, "icon.ico"),
                        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    # Logo horizontal: figura + texto
    logo = limpiar(Image.open(ORIGEN_LOGO))
    figura = logo.crop((0, 0, INICIO_TEXTO_LOGO, logo.height))
    texto = logo.crop((INICIO_TEXTO_LOGO, 0, logo.width, logo.height))

    claro = recortar(logo, 0.01)
    oscuro = Image.new("RGBA", logo.size, (0, 0, 0, 0))
    oscuro.paste(contorno(figura, 8), (0, 0))
    oscuro.paste(aclarar_oscuros(texto.copy()), (INICIO_TEXTO_LOGO, 0))
    oscuro = oscuro.crop(claro_caja(logo))

    cuadrado(extraer_estrella(logo), 256).save(os.path.join(DESTINO, "shuriken.png"))
    imagenes_instalador(icono, extraer_estrella(logo))

    ancho = 900
    for nombre, img in (("logo_light.png", claro), ("logo_dark.png", oscuro)):
        img = img.resize((ancho, round(img.height * ancho / img.width)), Image.LANCZOS)
        img.save(os.path.join(DESTINO, nombre))
    print("Recursos generados en", DESTINO)


def imagenes_instalador(icono, estrella):
    """
    Imágenes del asistente de Inno Setup (BMP de 24 bits, a doble resolución para pantallas HiDPI):
    - installer_large.bmp: panel lateral de las páginas de bienvenida y final.
    - installer_small.bmp: ícono de la esquina superior derecha de las demás páginas.
    """
    carpeta = os.path.join(RAIZ, "installer")
    os.makedirs(carpeta, exist_ok=True)

    ancho, alto = 328, 628
    panel = Image.new("RGBA", (ancho, alto), (7, 14, 38, 255))  # Azul marino del logo
    # Estrellas tenues de fondo
    for x, y, lado, giro in ((-40, 470, 220, 15), (210, 40, 120, 40), (230, 520, 90, 70)):
        sombra = estrella.resize((lado, lado), Image.LANCZOS).rotate(giro, resample=Image.BICUBIC)
        sombra.putalpha(sombra.getchannel("A").point(lambda v: v * 0.18))
        panel.alpha_composite(sombra, (x, y))
    ninja = contorno(icono, 14).resize((240, round(icono.height * 240 / icono.width)), Image.LANCZOS)
    panel.alpha_composite(ninja, ((ancho - ninja.width) // 2, (alto - ninja.height) // 2 - 20))
    panel.convert("RGB").save(os.path.join(carpeta, "installer_large.bmp"))

    chico = Image.new("RGBA", (110, 110), (255, 255, 255, 255))
    mini = cuadrado(icono, 100)
    chico.alpha_composite(mini, (5, 5))
    chico.convert("RGB").save(os.path.join(carpeta, "installer_small.bmp"))


def claro_caja(logo):
    """Misma caja de recorte que recortar(logo, 0.01), para que ambas variantes coincidan."""
    x0, y0, x1, y1 = logo.getchannel("A").getbbox()
    m = int(max(x1 - x0, y1 - y0) * 0.01)
    return x0 - m, y0 - m, x1 + m, y1 + m


if __name__ == "__main__":
    main()
