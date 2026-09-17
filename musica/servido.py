"""Servir solo el trozo de un PDF restringido.

**El agujero que cierra.** Hasta ahora `WAGTAILDOCS_SERVE_METHOD` no estaba
puesto, asi que Wagtail usaba su defecto, `redirect`: la URL del documento
redirige al fichero de media y cualquiera con el enlace se baja el PDF entero.
Decir «el alumno solo ve las paginas 10-13» era falso.

Ahora hay dos piezas:

- Un gancho `before_serve_document` que se niega a entregar un documento
  marcado como restringido. Es el portero.
- Esta vista, que entrega un PDF **nuevo** con solo las paginas del recorte. No
  toca el original: lo lee, copia el rango y lo devuelve en memoria.

**`pypdf` y no PyMuPDF.** PyMuPDF es AGPL y no esta en `requirements`; solo se
usa en scripts sueltos de `scripts/`. `pypdf` es BSD y hace lo unico que hace
falta aqui, que es copiar paginas. PyMuPDF haria falta el dia que generemos
miniaturas rasterizadas, y esa es una decision de licencia que no toca tomar
para esto.
"""

import io

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from wagtail import hooks
from wagtail.documents.models import Document

from martina_bescos_app.users.permisos import es_profesor
from musica.models import DocumentoRestringido, Recorte


@hooks.register("before_serve_document")
def servido_selectivo(document, request):
    """El portero. Bloquea lo restringido y aparta de en medio todo lo demas.

    **Las dos mitades son igual de importantes.**

    La primera: un PDF marcado no se entrega entero a nadie. Devolver 404 y no
    403 es deliberado, porque un 403 confirma que el fichero existe en esa URL y
    aqui el objetivo es que el PDF completo no figure como algo alcanzable. Se
    aplica tambien al profesorado: recortar SI necesita el documento entero, y
    para eso esta `pdf_para_recortar`, que pide sesion de profesor. Son dos
    puertas distintas a proposito.

    La segunda: **todo lo NO restringido se redirige al fichero, como antes.**
    Poner `WAGTAILDOCS_SERVE_METHOD = "serve_view"` hace que Wagtail sirva CADA
    documento a traves de Django, y su vista no atiende peticiones por rango:
    comprobado pidiendo `bytes=0-99` y recibiendo un 200 con el fichero entero.
    Para un PDF se nota poco; para los 43 audios del centro —101 MB, el mayor de
    23— significa que el navegador no puede mover la barra de reproduccion hasta
    haberlo descargado todo, y uno de los sitios donde eso duele es la pantalla
    de proyectar en clase.

    Redirigiendo aqui, la restriccion se aplica y el resto del sitio sigue
    sirviendose por el servidor web, con rangos y cache, exactamente igual que
    antes de todo esto.
    """
    if DocumentoRestringido.esta_restringido(document.pk):
        raise Http404("Este documento solo se puede ver por sus recortes.")

    if document.file:
        return redirect(document.file.url)


def pdf_del_recorte(request, pk):
    """Entrega un PDF con SOLO las paginas de este recorte.

    No comprueba permisos de usuario a proposito: un recorte es contenido
    publicado, igual que una imagen de una pagina publica. Lo que se protege no
    es el trozo, es el libro entero.

    El rectangulo NO se aplica aqui. Recortar la caja en el fichero obligaria a
    rasterizar o a reescribir el `MediaBox`, y el visor ya encuadra en cliente
    con el PDF vectorial intacto. Aqui lo unico que se acota son las paginas,
    que es lo que de verdad cambia cuanto material sale por la puerta.
    """
    from pypdf import PdfReader, PdfWriter

    recorte = get_object_or_404(Recorte, pk=pk)
    documento = recorte.documento
    if not documento.file:
        raise Http404("El documento no tiene fichero.")

    try:
        lector = PdfReader(documento.file.open("rb"))
    except Exception:
        # Un PDF corrupto o un fichero que no es un PDF no debe reventar con
        # 500: para quien lo pide es exactamente lo mismo que no estar.
        raise Http404("No se pudo leer el PDF.")

    total = len(lector.pages)
    desde, hasta = recorte.rango_paginas
    # Recortar contra el documento REAL: si alguien sustituyo el PDF por uno mas
    # corto, el rango apunta fuera y `pypdf` reventaria con IndexError.
    desde = max(1, min(desde, total))
    hasta = max(desde, min(hasta, total))

    escritor = PdfWriter()
    for indice in range(desde - 1, hasta):
        escritor.add_page(lector.pages[indice])

    buffer = io.BytesIO()
    escritor.write(buffer)
    buffer.seek(0)

    respuesta = FileResponse(buffer, content_type="application/pdf")
    # `inline` y no `attachment`: esto lo pide el visor para pintarlo, no un
    # humano para guardarlo.
    respuesta["Content-Disposition"] = (
        f'inline; filename="recorte-{recorte.pk}.pdf"'
    )
    return respuesta


@login_required
@user_passes_test(es_profesor)
def pdf_para_recortar(request, document_id):
    """El documento entero, solo para la pantalla de recorte.

    Para elegir un trozo hay que ver el libro entero: un recortador que solo
    enseñara los trozos ya recortados no serviría para nada. Por eso esta puerta
    existe, y por eso pide sesión de profesor, que es exactamente la misma
    condición que abre la pantalla de recorte.

    No es un rodeo a la restricción: la restricción dice que el PDF no se sirve
    por su URL pública, no que no se pueda trabajar con él. El profesor que lo
    subió ya tiene el fichero.
    """
    documento = get_object_or_404(Document, pk=document_id)
    if not documento.file:
        raise Http404("El documento no tiene fichero.")
    respuesta = FileResponse(
        documento.file.open("rb"), content_type="application/pdf"
    )
    respuesta["Content-Disposition"] = 'inline; filename="documento.pdf"'
    return respuesta
