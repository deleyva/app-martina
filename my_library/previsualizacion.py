"""Qué hace falta para pintar la miniatura de un medio. Datos, no HTML.

**Por qué no devuelve HTML.** Tailwind solo escanea las rutas de
`tailwind.config.js`, y ahí están las plantillas y `martina_bescos_app/**/*.py`,
pero NO `my_library/*.py` ni `clases/*.py`. Una clase escrita en una cadena de
Python de este paquete no llega al CSS compilado, así que el marcado vive en
`my_library/partials/miniatura.html` y aquí solo se decide qué enseñar.

**Las imágenes van por URL firmada, no por `get_rendition()`.** Generar la
rendition dentro de la petición que pinta la lista significa crear 283 ficheros
antes de devolver una línea de HTML en un libro como *Ukulele Aerobics*. Con
`generate_image_url` la vista solo firma una URL y el fichero se genera en la
petición del `<img>`, que con `loading="lazy"` solo ocurre para lo que el
profesor llega a ver. Necesita la ruta `images/` registrada en `config/urls.py`.

**Los PDF no se rasterizan en el servidor.** Haría falta PyMuPDF, que es AGPL y
está descartada a conciencia (ver `musica/servido.py`). La primera página se
pinta con pdf.js en el navegador, que ya está cargado en estas pantallas: aquí
solo se dice de qué URL sacarla y qué trozo interesa.
"""

from django.urls import reverse
from wagtail.images.views.serve import generate_image_url

from my_library import medios

# El doble del tamaño de pantalla, para que no se vea borrosa en retina.
RENDITION = "fill-192x144"


def datos_de_miniatura(objeto, modelo=None):
    """`{tipo, titulo, src, pdf_url, recorte}` para `miniatura.html`.

    `tipo` es siempre uno de los conocidos por la plantilla, así que un medio
    raro cae en una caja con su icono y nunca en un hueco vacío.
    """
    if objeto is None:
        return {"tipo": "desconocido", "titulo": ""}

    if modelo is None:
        modelo = objeto.__class__.__name__.lower()

    clave = medios.clave_de(objeto, modelo)
    titulo = getattr(objeto, "title", None) or getattr(objeto, "nombre", "") or ""
    datos = {"tipo": "desconocido", "titulo": str(titulo)}

    if clave == "images":
        try:
            datos.update(tipo="imagen", src=generate_image_url(objeto, RENDITION))
        except Exception:
            # Un fichero que ya no está en disco no puede tumbar la pantalla
            # entera de preparar una clase.
            datos["tipo"] = "imagen_rota"

    elif clave == "embeds":
        datos.update(tipo="video", src=getattr(objeto, "thumbnail_url", "") or "")

    elif clave == "recortes":
        # El PDF ya llega cortado al rango, así que la página que interesa es
        # siempre la primera. El rectángulo, si lo hay, lo aplica el navegador.
        datos.update(
            tipo="recorte",
            pdf_url=reverse("musica:pdf_del_recorte", args=[objeto.pk]),
            pagina=1,
            recorte=_rectangulo(objeto),
        )

    elif clave == "pdfs":
        datos.update(tipo="pdf", pdf_url=_url_de_fichero(objeto), pagina=1)

    elif clave == "audios":
        datos["tipo"] = "audio"
    elif clave == "gp_files":
        datos["tipo"] = "tablatura"
    elif clave in ("enlaces", "external_links"):
        datos["tipo"] = "enlace"

    return datos


def _rectangulo(recorte):
    """`x0,y0,x1,y1` normalizados, o `None` si el recorte es la página entera."""
    lados = (recorte.rect_x0, recorte.rect_y0, recorte.rect_x1, recorte.rect_y1)
    if any(lado is None for lado in lados):
        return None
    return ",".join(str(lado) for lado in lados)


def _url_de_fichero(documento):
    """La URL por la que Wagtail sirve el documento, o vacío si no hay fichero.

    Se pide `url` y no `file.url` porque un documento restringido solo sale por
    el portero de `musica.servido`, y esa es justo la URL que lo respeta.
    """
    try:
        return documento.url or ""
    except (AttributeError, ValueError):
        return ""
