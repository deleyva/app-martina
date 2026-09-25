"""Vistas de la libreta. TINY VIEWS: el orden, las hojas y el PDF viven en los modelos.

Todas piden sesión y nada más: la libreta la componen profesores y alumnado por
igual, cada uno la suya. La propiedad se comprueba en `Libreta.del_usuario`
(404, no 403). Las que devuelven la lista de elementos responden al parcial
cuando la petición viene de HTMX y redirigen si no, para que el formulario
funcione también sin JavaScript.
"""

from __future__ import annotations

import contextlib

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.images import ImageFile
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_POST

from . import fuentes
from . import plantillas
from .models import Elemento
from .models import Libreta

TAMANO_MAXIMO_DE_IMAGEN = 15 * 1024 * 1024


def _elemento_del_usuario(request, pk) -> Elemento:
    elemento = get_object_or_404(Elemento.objects.select_related("libreta"), pk=pk)
    Libreta.del_usuario(request.user, elemento.libreta_id)
    return elemento


def _lista(request, libreta):
    """El parcial de elementos si es HTMX; la página entera si no."""
    if request.headers.get("HX-Request"):
        return render(
            request,
            "libreta/partials/elementos.html",
            {
                "libreta": libreta,
                "elementos": libreta.elementos_ordenados(),
                "htmx": True,
            },
        )
    return redirect("libreta:editar", pk=libreta.pk)


@login_required
def index(request):
    return render(
        request,
        "libreta/index.html",
        {"libretas": Libreta.objects.filter(user=request.user)},
    )


@login_required
@require_POST
def crear(request):
    libreta = Libreta.objects.create(
        user=request.user,
        titulo=(request.POST.get("titulo") or "").strip()[:120] or "Libreta de música",
        subtitulo=(request.POST.get("subtitulo") or "").strip()[:120],
    )
    return redirect("libreta:editar", pk=libreta.pk)


@login_required
def editar(request, pk):
    libreta = Libreta.del_usuario(request.user, pk)
    return render(
        request,
        "libreta/editar.html",
        {
            "libreta": libreta,
            "elementos": libreta.elementos_ordenados(),
            "generadas": plantillas.disponibles(),
            "plantillas": fuentes.plantillas(),
        },
    )


@login_required
@require_POST
def ajustes(request, pk):
    libreta = Libreta.del_usuario(request.user, pk)
    libreta.titulo = (request.POST.get("titulo") or "").strip()[:120] or libreta.titulo
    libreta.subtitulo = (request.POST.get("subtitulo") or "").strip()[:120]
    libreta.portada = "portada" in request.POST
    libreta.indice = "indice" in request.POST
    libreta.hoja_nueva_por_seccion = "hoja_nueva_por_seccion" in request.POST
    with contextlib.suppress(ValueError):
        libreta.primera_pagina = max(1, int(request.POST.get("primera_pagina", 1)))
    libreta.save()
    messages.success(request, "Ajustes guardados.")
    return redirect("libreta:editar", pk=libreta.pk)


@login_required
@require_POST
def borrar(request, pk):
    libreta = Libreta.del_usuario(request.user, pk)
    libreta.delete()
    messages.success(request, "Libreta borrada.")
    return redirect("libreta:index")


@login_required
@require_POST
def anadir(request, pk):
    """Un elemento nuevo: `tipo` = plantilla | documento | imagen | subida | texto."""
    libreta = Libreta.del_usuario(request.user, pk)
    tipo = request.POST.get("tipo", "")
    posicion = request.POST.get("posicion", "final")
    titulo = (request.POST.get("titulo") or "").strip()
    try:
        libreta.insertar(_elemento_nuevo(request, tipo, titulo), posicion)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    return _lista(request, libreta)


def _elemento_nuevo(request, tipo, titulo) -> Elemento:
    if tipo == "plantilla":
        return Elemento.desde_plantilla(request.POST.get("clave", ""), titulo or None)
    if tipo in ("documento", "imagen"):
        objeto = fuentes.medio(tipo, request.POST.get("pk"))
        if objeto is None:
            msg = "Ese contenido no existe o no se puede fotocopiar."
            raise ValidationError(msg)
        return Elemento.desde_medio(objeto, titulo or None)
    if tipo == "subida":
        return Elemento.desde_medio(_guardar_imagen(request), titulo or None)
    if tipo == "texto":
        return Elemento(
            titulo=titulo[:120] or "Texto",
            texto=request.POST.get("texto", "").strip(),
        )
    msg = "No sé qué añadir."
    raise ValidationError(msg)


def _es_imagen(fichero) -> bool:
    from willow.image import Image as ImagenWillow
    from willow.image import UnrecognisedImageFormatError

    try:
        ImagenWillow.open(fichero)
    except UnrecognisedImageFormatError:
        return False
    return True


def _guardar_imagen(request):
    """La imagen subida queda como `Image` de Wagtail, del propio usuario."""
    from wagtail.images import get_image_model

    fichero = request.FILES.get("fichero")
    if fichero is None:
        msg = "Falta la imagen."
        raise ValidationError(msg)
    if fichero.size > TAMANO_MAXIMO_DE_IMAGEN:
        msg = "La imagen pasa de 15 MB."
        raise ValidationError(msg)
    # Se mira ANTES de construir el modelo: Wagtail lee ancho y alto en
    # `post_init`, así que con un fichero que no es imagen ni siquiera se
    # llega a `full_clean`.
    if not _es_imagen(fichero):
        msg = "Eso no es una imagen que pueda usar (PNG, JPG, WEBP…)."
        raise ValidationError(msg)
    fichero.seek(0)
    imagen = get_image_model()(
        title=fichero.name[:255],
        file=ImageFile(fichero, name=fichero.name),
        uploaded_by_user=request.user,
    )
    imagen.full_clean(exclude=["collection"])
    imagen.save()
    return imagen


@login_required
def buscar(request, pk):
    libreta = Libreta.del_usuario(request.user, pk)
    texto = request.GET.get("q", "")
    return render(
        request,
        "libreta/partials/resultados.html",
        {"libreta": libreta, "q": texto, "resultados": fuentes.buscar(texto)},
    )


@login_required
@require_POST
def elemento_guardar(request, pk):
    elemento = _elemento_del_usuario(request, pk)
    elemento.titulo = (request.POST.get("titulo") or "").strip()[
        :120
    ] or elemento.titulo
    with contextlib.suppress(ValueError):
        elemento.copias = max(1, int(request.POST.get("copias", elemento.copias)))
    elemento.save(update_fields=["titulo", "copias"])
    return _lista(request, elemento.libreta)


@login_required
@require_POST
def elemento_mover(request, pk):
    elemento = _elemento_del_usuario(request, pk)
    elemento.mover(request.POST.get("direccion", ""))
    return _lista(request, elemento.libreta)


@login_required
@require_POST
def elemento_borrar(request, pk):
    elemento = _elemento_del_usuario(request, pk)
    libreta = elemento.libreta
    elemento.borrar()
    return _lista(request, libreta)


@login_required
def pdf(request, pk):
    libreta = Libreta.del_usuario(request.user, pk)
    respuesta = HttpResponse(libreta.pdf(), content_type="application/pdf")
    respuesta["Content-Disposition"] = (
        f'inline; filename="{libreta.nombre_de_fichero()}"'
    )
    return respuesta


@login_required
def pedido(request, pk):
    libreta = Libreta.del_usuario(request.user, pk)
    respuesta = HttpResponse(libreta.pedido(), content_type="application/pdf")
    respuesta["Content-Disposition"] = 'inline; filename="pedido-fotocopias.pdf"'
    return respuesta
