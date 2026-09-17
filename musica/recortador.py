"""Importar un método: del PDF al libro troceado, sin salir del frontend.

**El flujo que resuelve**, de principio a fin y sin tocar el admin de Wagtail:

1. `/musica/importar/` — subir el PDF y crear el libro vacío.
2. `/musica/recortar/<doc>/?libro=<id>` — la pantalla de trabajo: se ve el PDF,
   se marca cada trozo (rango de páginas o recuadro), se le pone nombre y entra
   como capítulo del libro.
3. Ahí mismo se corrige lo ya hecho, se reordena el libro y se marca el
   documento como restringido.

**Vistas delgadas.** Solo leen el formulario, llaman al modelo y devuelven el
parcial. La colocación vive en `_colocar`, la validación en `Recorte.clean()` y
el orden en el StreamField del libro.

**Por qué el recorte no tiene campo de orden.** Su posición es la que ocupa
DENTRO DE UN LIBRO, y eso ya lo guarda el StreamField. La lista de la izquierda
se ordena por página, que es como buscas uno mientras troceas; el orden de
estudio se arrastra en el panel del libro.
"""

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from wagtail.documents.models import Document

from martina_bescos_app.users.permisos import es_profesor
from musica.models import (
    DocumentoRestringido,
    LibroDeEstudioPage,
    MusicLibraryIndexPage,
    Recorte,
    RecursoPage,
)

logger = logging.getLogger(__name__)

EXTENSIONES_PDF = (".pdf",)


# === Ayudantes ===


def _documento_pdf(document_id):
    """El documento, siempre que sea un PDF.

    Un `.mp3` o un `.gp5` no tienen páginas: dejar que se abra el recortador
    sobre ellos produciría recortes que no se pueden pintar.
    """
    documento = get_object_or_404(Document, pk=document_id)
    nombre = documento.file.name.lower() if documento.file else ""
    if not nombre.endswith(EXTENSIONES_PDF):
        raise Http404("Solo se pueden recortar PDF.")
    return documento


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _decimal(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _clave_de_bloque(bloque):
    """Identifica un bloque del libro de forma estable.

    Lleva el tipo delante porque los pk de `Page` y de `Recorte` son de tablas
    distintas y se pisan: sin el prefijo, el recorte 5 y la página 5 serían el
    mismo bloque al reordenar.
    """
    valor = bloque.value
    if valor is None:
        return None
    return f"{bloque.block_type}:{valor.pk}"


def _capitulos_del_libro(libro):
    """`[{clave, tipo, titulo, detalle}]` en el orden de estudio."""
    if libro is None:
        return []
    filas = []
    for bloque in libro.capitulos:
        clave = _clave_de_bloque(bloque)
        if clave is None:
            continue
        valor = bloque.value
        if bloque.block_type == "recorte":
            filas.append({
                "clave": clave,
                "tipo": "recorte",
                "titulo": valor.nombre,
                "detalle": valor.etiqueta_de_paginas,
                "recorte_id": valor.pk,
            })
        else:
            filas.append({
                "clave": clave,
                "tipo": "pagina",
                "titulo": valor.title,
                "detalle": "página",
                "recorte_id": None,
            })
    return filas


def _contexto_de_lista(documento, libro=None):
    """Lo que necesita el parcial de la lista, con el libro ya cruzado.

    El cruce es lo que contesta a «¿por dónde iba?»: sin saber cuáles ya son
    capítulo, a mitad de un método de cincuenta páginas no hay forma de saberlo
    sin abrir el libro en otra pestaña.
    """
    capitulos = _capitulos_del_libro(libro)
    posicion = {
        fila["recorte_id"]: n + 1
        for n, fila in enumerate(capitulos)
        if fila["recorte_id"]
    }
    recortes = list(
        Recorte.objects.filter(documento=documento).order_by("pagina_desde", "nombre")
    )
    for recorte in recortes:
        recorte.posicion_en_el_libro = posicion.get(recorte.pk)

    return {
        "documento": documento,
        "recortes": recortes,
        "libro": libro,
        "capitulos": capitulos,
        "restringido": DocumentoRestringido.esta_restringido(documento.pk),
    }


def _libro_de_la_peticion(request):
    """El libro al que está atada la pantalla, o None.

    Viaja en la query (`?libro=`) y no en sesión a propósito: así el enlace de
    «seguir con este método» se puede guardar en marcadores y lleva al mismo
    sitio.
    """
    libro_id = _entero(request.GET.get("libro") or request.POST.get("libro"))
    if not libro_id:
        return None
    return LibroDeEstudioPage.objects.filter(pk=libro_id).first()


def _lista(request, documento, **extra):
    contexto = _contexto_de_lista(documento, _libro_de_la_peticion(request))
    contexto.update(extra)
    return render(request, "musica/partials/lista_de_recortes.html", contexto)


# === Índice de importación ===


@login_required
@user_passes_test(es_profesor)
def importar(request):
    """La portada del flujo: subir un PDF, crear un libro, seguir con lo empezado."""
    documentos = (
        Document.objects.filter(file__iendswith=".pdf")
        .order_by("-created_at")[:40]
    )
    con_recortes = set(
        Recorte.objects.values_list("documento_id", flat=True).distinct()
    )
    restringidos = set(
        DocumentoRestringido.objects.filter(solo_por_recorte=True).values_list(
            "documento_id", flat=True
        )
    )
    for documento in documentos:
        documento.tiene_recortes = documento.pk in con_recortes
        documento.esta_restringido = documento.pk in restringidos

    return render(
        request,
        "musica/importar.html",
        {
            "documentos": documentos,
            "libros": LibroDeEstudioPage.objects.live().order_by("title"),
        },
    )


@login_required
@user_passes_test(es_profesor)
@require_POST
def subir_pdf(request):
    """Sube un PDF y lleva directo a recortarlo.

    Va al recortador y no de vuelta al índice porque subir un método es el paso
    previo a trocearlo, nunca un fin en sí mismo.
    """
    fichero = request.FILES.get("file")
    titulo = (request.POST.get("title") or "").strip()

    if fichero is None:
        return render(request, "musica/partials/aviso.html",
                      {"error": "No has elegido ningún fichero."})
    if not fichero.name.lower().endswith(EXTENSIONES_PDF):
        return render(request, "musica/partials/aviso.html",
                      {"error": "Solo se pueden recortar PDF."})

    # Se aligera ANTES de guardar, no después: guardar y recomprimir dejaría el
    # fichero pesado en disco entre las dos operaciones, y un fallo a mitad
    # dejaría el original servido como si nada.
    from django.core.files.base import ContentFile

    from musica.optimizar import optimizar

    datos, informe = optimizar(fichero.read())
    documento = Document.objects.create(
        title=titulo[:255] or fichero.name,
        file=ContentFile(datos, name=fichero.name),
    )
    logger.info("PDF subido %s: %s", documento.pk, informe)
    # Por `messages` y no en el parcial: la respuesta es una redirección, así
    # que el aviso tiene que sobrevivir al salto a la pantalla de recorte.
    messages.success(request, f"«{documento.title}» subido. {informe}")
    libro_id = _entero(request.POST.get("libro"))
    destino = f"/musica/recortar/{documento.pk}/"
    if libro_id:
        destino += f"?libro={libro_id}"
    # `HX-Redirect`: el formulario va por HTMX, y sin esto el navegador se
    # quedaría en el índice con el parcial intercambiado.
    respuesta = HttpResponse(status=204)
    respuesta["HX-Redirect"] = destino
    return respuesta


@login_required
@user_passes_test(es_profesor)
@require_POST
def crear_libro(request):
    """Crea un libro de estudio vacío bajo el índice de recursos musicales."""
    from django.utils.text import slugify

    titulo = (request.POST.get("titulo") or "").strip()
    if not titulo:
        return render(request, "musica/partials/aviso.html",
                      {"error": "El libro necesita un título."})

    padre = MusicLibraryIndexPage.objects.first()
    if padre is None:
        return render(request, "musica/partials/aviso.html",
                      {"error": "No hay índice de recursos musicales donde colgarlo."})

    slug = slugify(titulo)[:255]
    if padre.get_children().filter(slug=slug).exists():
        return render(request, "musica/partials/aviso.html",
                      {"error": f"Ya hay un libro con el slug «{slug}»."})

    libro = LibroDeEstudioPage(title=titulo[:255], slug=slug, capitulos=[])
    padre.add_child(instance=libro)
    libro.save_revision().publish()

    respuesta = HttpResponse(status=204)
    respuesta["HX-Redirect"] = "/musica/importar/"
    return respuesta


# === La pantalla de trabajo ===


@login_required
@user_passes_test(es_profesor)
def recortador(request, document_id):
    """PDF a la izquierda, formulario y libro a la derecha."""
    documento = _documento_pdf(document_id)
    libro = _libro_de_la_peticion(request)
    contexto = _contexto_de_lista(documento, libro)
    contexto.update(
        libros=LibroDeEstudioPage.objects.live().order_by("title"),
        paginas=RecursoPage.objects.live().order_by("title"),
    )
    return render(request, "musica/recortador.html", contexto)


def _rellenar(recorte, request):
    """Vuelca el formulario sobre un recorte, sin guardar."""
    recorte.nombre = (request.POST.get("nombre") or "").strip()[:200]
    recorte.pagina_desde = _entero(request.POST.get("pagina_desde")) or 1
    recorte.pagina_hasta = _entero(request.POST.get("pagina_hasta"))
    recorte.pagina_offset_impresa = _entero(request.POST.get("pagina_offset_impresa"))
    recorte.rect_x0 = _decimal(request.POST.get("rect_x0"))
    recorte.rect_y0 = _decimal(request.POST.get("rect_y0"))
    recorte.rect_x1 = _decimal(request.POST.get("rect_x1"))
    recorte.rect_y1 = _decimal(request.POST.get("rect_y1"))
    return recorte


def _validar(recorte, request, documento):
    """Devuelve la respuesta de error, o None si el recorte vale.

    El error vuelve en la misma lista y no en una página aparte: se está
    dibujando, y perder el sitio es perder el trabajo hecho.
    """
    from django.core.exceptions import ValidationError

    if not recorte.nombre:
        return _lista(request, documento,
                      error="Ponle un nombre: es por lo que lo vas a buscar luego.")
    try:
        recorte.full_clean(exclude=["documento"])
    except ValidationError as e:
        return _lista(request, documento, error=" ".join(
            mensaje for mensajes in e.message_dict.values() for mensaje in mensajes
        ))
    return None


@login_required
@user_passes_test(es_profesor)
@require_POST
def crear_recorte(request, document_id):
    """Crea el recorte y lo coloca donde diga el formulario."""
    documento = _documento_pdf(document_id)
    recorte = _rellenar(Recorte(documento=documento), request)

    fallo = _validar(recorte, request, documento)
    if fallo is not None:
        return fallo

    recorte.save()
    aviso = _colocar(
        recorte,
        request.POST.get("destino") or "suelto",
        _entero(request.POST.get("destino_id")),
    )
    return _lista(request, documento, aviso=aviso)


@login_required
@user_passes_test(es_profesor)
@require_POST
def editar_recorte(request, pk):
    """Corrige un recorte que ya existe, sin borrarlo ni rehacerlo.

    Importa que sea una edición y no un borrar-y-crear: el recorte puede ser ya
    capítulo de varios libros, y rehacerlo lo sacaría de todos ellos y lo
    mandaría al final del que se elija.
    """
    recorte = get_object_or_404(Recorte, pk=pk)
    documento = recorte.documento
    _rellenar(recorte, request)

    fallo = _validar(recorte, request, documento)
    if fallo is not None:
        return fallo

    recorte.save()
    return _lista(request, documento, aviso=f"«{recorte.nombre}» actualizado.")


def _colocar(recorte, destino, destino_id):
    """Engancha el recorte donde toque. Devuelve el aviso para la pantalla.

    Las dos formas escriben en StreamFields distintos y por eso no se unifican:
    un capítulo de libro es un bloque de `capitulos`, y un adjunto de una página
    es un bloque de `attachments`. La forma del bloque también difiere, que es
    justo el detalle que conviene tener en un solo sitio.
    """
    if destino == "libro" and destino_id:
        libro = LibroDeEstudioPage.objects.filter(pk=destino_id).first()
        if libro is None:
            return f"«{recorte.nombre}» creado, pero ese libro ya no existe."
        libro.capitulos.append(("recorte", recorte))
        libro.save()
        libro.save_revision().publish()
        return f"«{recorte.nombre}» añadido a «{libro.title}»."

    if destino == "capitulo" and destino_id:
        pagina = RecursoPage.objects.filter(pk=destino_id).first()
        if pagina is None:
            return f"«{recorte.nombre}» creado, pero esa página ya no existe."
        pagina.attachments.append(("recorte", {"recorte": recorte}))
        pagina.save()
        pagina.save_revision().publish()
        return f"«{recorte.nombre}» adjuntado a «{pagina.title}»."

    return f"«{recorte.nombre}» creado. Está suelto: aún no es capítulo de nada."


@login_required
@user_passes_test(es_profesor)
@require_POST
def borrar_recorte(request, pk):
    """Borra un recorte. El PDF no se toca: el recorte solo era un puntero."""
    from django.db.models import ProtectedError

    recorte = get_object_or_404(Recorte, pk=pk)
    documento = recorte.documento
    nombre = recorte.nombre

    try:
        recorte.delete()
    except ProtectedError:
        return _lista(request, documento, error=f"«{nombre}» está en uso.")

    return _lista(request, documento, aviso=f"«{nombre}» borrado. El PDF sigue intacto.")


@login_required
@user_passes_test(es_profesor)
@require_POST
def reordenar_libro(request, libro_id):
    """Reordena los capítulos del libro según las claves que llegan.

    Los bloques que no vengan en la lista se quedan AL FINAL en vez de perderse.
    Es la diferencia entre una petición a medias que descoloca y una que borra
    capítulos sin que nadie se entere.
    """
    libro = get_object_or_404(LibroDeEstudioPage, pk=libro_id)
    try:
        claves = json.loads(request.POST.get("claves") or "[]")
    except ValueError:
        claves = []

    por_clave = {}
    for bloque in libro.capitulos:
        clave = _clave_de_bloque(bloque)
        if clave is not None:
            por_clave[clave] = bloque

    nuevos = []
    for clave in claves:
        bloque = por_clave.pop(clave, None)
        if bloque is not None:
            nuevos.append((bloque.block_type, bloque.value))
    for bloque in por_clave.values():
        nuevos.append((bloque.block_type, bloque.value))

    libro.capitulos = nuevos
    libro.save()
    libro.save_revision().publish()
    return HttpResponse(status=204)


@login_required
@user_passes_test(es_profesor)
@require_POST
def alternar_restriccion(request, document_id):
    """Marca o desmarca el PDF como servible solo por sus recortes."""
    documento = _documento_pdf(document_id)

    if DocumentoRestringido.esta_restringido(documento.pk):
        DocumentoRestringido.objects.filter(documento=documento).delete()
        aviso = "El PDF vuelve a servirse entero."
    else:
        DocumentoRestringido.objects.update_or_create(
            documento=documento,
            defaults={"solo_por_recorte": True,
                      "motivo": (request.POST.get("motivo") or "")[:200]},
        )
        aviso = "El PDF ya solo se sirve por sus recortes."

    return _lista(request, documento, aviso=aviso)


@login_required
@user_passes_test(es_profesor)
def lista_de_recortes(request, document_id):
    """El parcial de la lista, para refrescarla sin recargar la pantalla."""
    return _lista(request, _documento_pdf(document_id))
