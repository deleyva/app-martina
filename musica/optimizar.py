"""Aligerar un PDF escaneado al subirlo.

**El problema, medido.** Un método escaneado de 56 páginas ocupa 13,7 MB. Desde
que los documentos se sirven por la vista de Wagtail —lo que hace real la
restricción— cada apertura son 13,7 MB por Django, y PDF.js no puede pedir el
fichero por trozos porque esa vista no atiende peticiones por rango. En local,
con el servidor de desarrollo, ese método no llegaba a abrirse.

**Qué hace.** Recomprime las imágenes de cada página y punto: no rasteriza la
página entera, así que el texto y los vectores que hubiera se quedan como
estaban. En un escaneo las imágenes SON la página, y ahí está todo el peso.

**Los números, sobre ese mismo método** (13,7 MB de partida):

| lado máx. | calidad | resultado |
|-----------|---------|-----------|
| 1600      | 78      | 12,4 MB   |
| 1300      | 75      |  9,2 MB   |
| **1100**  | **72**  | **7,0 MB** |
| 900       | 68      |  4,8 MB   |

Se eligió 1100/72 mirando los píxeles, no el porcentaje: a 150 dpi, ampliada,
la notación y la letra son indistinguibles del original. A 900 todavía se lee,
pero en partitura conviene el margen.

**`pikepdf` y no PyMuPDF.** PyMuPDF haría esto en cuatro líneas, pero es AGPL, y
la AGPL obliga a ofrecer el código fuente a quien use el servicio por red. Para
un sitio que da la cara a internet eso es una obligación de verdad, no un
tecnicismo. `pikepdf` es MPL-2.0 y `Pillow` ya estaba.
"""

import io
import logging

logger = logging.getLogger(__name__)

# Lado mayor en píxeles y calidad JPEG. Ver la tabla del docstring.
LADO_MAXIMO = 1100
CALIDAD = 72

# Por debajo de esto no se toca nada: recomprimir un PDF que ya es ligero gasta
# tiempo de subida para ahorrar kilobytes.
MINIMO_PARA_TOCAR = 2 * 1024 * 1024


class Informe:
    """Qué pasó, para poder contarlo en pantalla."""

    def __init__(self, antes, despues, imagenes, motivo=""):
        self.antes = antes
        self.despues = despues
        self.imagenes = imagenes
        self.motivo = motivo

    @property
    def optimizado(self):
        return self.despues < self.antes

    @property
    def ahorro_pct(self):
        if not self.antes:
            return 0
        return round((1 - self.despues / self.antes) * 100)

    def __str__(self):
        if not self.optimizado:
            return self.motivo or "No hacía falta aligerarlo."
        return (
            f"Aligerado de {self.antes / 1e6:.1f} MB a {self.despues / 1e6:.1f} MB "
            f"({self.ahorro_pct}% menos, {self.imagenes} imágenes)."
        )


def _recomprimir(pdf, pagina, nombre, obj):
    """Devuelve el stream nuevo, o None si no merece la pena cambiarlo."""
    import pikepdf
    from PIL import Image

    try:
        original = bytes(obj.read_raw_bytes())
        pil = pikepdf.PdfImage(obj).as_pil_image()
    except Exception:
        # Imágenes con filtros raros (JBIG2, CCITT, máscaras) se dejan como
        # están: hacerlas pasar por Pillow las estropearía más de lo que pesan.
        return None

    if pil.mode not in ("RGB", "L"):
        pil = pil.convert("RGB")

    ancho, alto = pil.size
    escala = min(1.0, LADO_MAXIMO / max(ancho, alto))
    if escala < 1.0:
        pil = pil.resize((int(ancho * escala), int(alto * escala)), Image.LANCZOS)

    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=CALIDAD, optimize=True, progressive=True)
    datos = buf.getvalue()

    # Si no sale más pequeño, no se toca. Recomprimir por recomprimir solo
    # añade una generación de pérdida.
    if len(datos) >= len(original):
        return None

    nuevo = pikepdf.Stream(pdf, datos)
    nuevo.Type = pikepdf.Name.XObject
    nuevo.Subtype = pikepdf.Name.Image
    nuevo.Width, nuevo.Height = pil.size
    nuevo.ColorSpace = (
        pikepdf.Name.DeviceGray if pil.mode == "L" else pikepdf.Name.DeviceRGB
    )
    nuevo.BitsPerComponent = 8
    nuevo.Filter = pikepdf.Name.DCTDecode
    return nuevo


def optimizar(datos):
    """`(bytes, Informe)`. Nunca lanza: si algo falla, devuelve el original.

    Que no lance es el requisito. Esto corre en mitad de una subida, y un PDF
    raro no puede costarle a nadie el fichero que acaba de elegir: en el peor
    caso se guarda tal cual y se avisa.
    """
    antes = len(datos)
    if antes < MINIMO_PARA_TOCAR:
        return datos, Informe(antes, antes, 0, "Ya era ligero: se guarda tal cual.")

    try:
        import pikepdf
    except ImportError:  # pragma: no cover
        return datos, Informe(antes, antes, 0, "Falta pikepdf: se guarda tal cual.")

    try:
        pdf = pikepdf.open(io.BytesIO(datos))
    except Exception as e:
        logger.warning("No se pudo abrir el PDF para aligerarlo: %s", e)
        return datos, Informe(antes, antes, 0, "No se pudo leer: se guarda tal cual.")

    tocadas = 0
    try:
        for pagina in pdf.pages:
            recursos = pagina.get("/Resources")
            xobjects = recursos.get("/XObject") if recursos is not None else None
            if xobjects is None:
                continue
            for nombre in list(xobjects.keys()):
                obj = xobjects[nombre]
                if obj.get("/Subtype") != pikepdf.Name.Image:
                    continue
                nuevo = _recomprimir(pdf, pagina, nombre, obj)
                if nuevo is not None:
                    xobjects[nombre] = nuevo
                    tocadas += 1

        salida = io.BytesIO()
        pdf.save(
            salida,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )
    except Exception as e:
        logger.warning("Falló el aligerado del PDF: %s", e)
        return datos, Informe(antes, antes, 0, "Falló el aligerado: se guarda tal cual.")

    resultado = salida.getvalue()
    if len(resultado) >= antes:
        return datos, Informe(antes, antes, 0, "No se podía aligerar más.")

    return resultado, Informe(antes, len(resultado), tocadas)
