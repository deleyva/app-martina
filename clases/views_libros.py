"""Pantallas de los libros que dan clase.

Vistas finas: todo lo que decide algo vive en `clases.libros_de_grupo`. Aquí solo
se comprueba el permiso, se traduce el POST y se pinta.

El permiso es siempre el mismo y por eso está en un solo sitio: manda el grupo,
no el profesor. La selección y el orden de un libro son del grupo (decisión del
principal, 2026-09-08), así que cualquier profesor del grupo ve y toca lo mismo.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from wagtail.models import Page

from clases import libros_de_grupo
from clases.models import ClassSession, ClassSessionItem, Group, GroupBook, GroupBookItem
from clases.views import is_staff


def _grupo_del_profesor(request, group_id):
    """El grupo, si quien pregunta le da clase. Si no, 404."""
    grupo = get_object_or_404(Group, pk=group_id)
    if not grupo.teachers.filter(pk=request.user.pk).exists():
        from django.http import Http404

        raise Http404("No das clase a este grupo.")
    return grupo


def _libro_del_profesor(request, pk):
    group_book = get_object_or_404(GroupBook.objects.select_related("group", "libro"), pk=pk)
    _grupo_del_profesor(request, group_book.group_id)
    return group_book


# =============================================================================
# ASIGNAR LIBROS A UN GRUPO
# =============================================================================


@login_required
@user_passes_test(is_staff)
def group_books_index(request, group_id):
    """Los libros del grupo, por secciones, con su avance."""
    grupo = _grupo_del_profesor(request, group_id)

    asignados = []
    for group_book in libros_de_grupo.libros_activos(grupo):
        vistos, total = libros_de_grupo.progreso(group_book)
        asignados.append(
            {
                "group_book": group_book,
                "vistos": vistos,
                "total": total,
                "porcentaje": round(100 * vistos / total) if total else 0,
            }
        )

    inactivos = grupo.books.filter(activo=False).select_related("libro")
    ya_asignados = set(grupo.books.values_list("libro_id", flat=True))
    disponibles = [
        libro for libro in libros_de_grupo.libros_disponibles() if libro.pk not in ya_asignados
    ]

    return render(
        request,
        "clases/group_books/index.html",
        {
            "group": grupo,
            "asignados": asignados,
            "inactivos": inactivos,
            "disponibles": disponibles,
            "secciones": GroupBook.SECCIONES,
            "modos": GroupBook.MODOS,
        },
    )


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def group_book_add(request, group_id):
    """Asigna un libro al grupo. No crea ni una fila de material."""
    grupo = _grupo_del_profesor(request, group_id)
    libro = get_object_or_404(Page, pk=request.POST.get("libro"))
    seccion = request.POST.get("seccion")
    modo = request.POST.get("modo", GroupBook.SECUENCIAL)

    if seccion not in dict(GroupBook.SECCIONES):
        messages.error(request, "Esa sección no existe.")
        return redirect("clases:group_books_index", group_id=grupo.pk)

    group_book, creado = GroupBook.objects.get_or_create(
        group=grupo,
        libro=libro,
        defaults={"seccion": seccion, "modo": modo, "added_by": request.user},
    )
    if creado:
        messages.success(request, f"«{libro.title}» asignado a {grupo.name}.")
    else:
        messages.info(request, f"«{libro.title}» ya estaba asignado a {grupo.name}.")
    return redirect("clases:group_book_items", pk=group_book.pk)


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def group_book_update(request, pk):
    """Cambia sección, modo o si sigue activo."""
    group_book = _libro_del_profesor(request, pk)

    seccion = request.POST.get("seccion")
    if seccion in dict(GroupBook.SECCIONES):
        group_book.seccion = seccion
    modo = request.POST.get("modo")
    if modo in dict(GroupBook.MODOS):
        group_book.modo = modo
    if "activo" in request.POST:
        group_book.activo = request.POST.get("activo") == "1"
    group_book.save()

    messages.success(request, f"«{group_book.libro.title}» actualizado.")
    return redirect("clases:group_books_index", group_id=group_book.group_id)


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def group_book_remove(request, pk):
    """Quita el libro del grupo. Se lleva su avance, y por eso se avisa antes."""
    group_book = _libro_del_profesor(request, pk)
    group_id, titulo = group_book.group_id, group_book.libro.title
    group_book.delete()
    messages.success(request, f"«{titulo}» ya no está asignado a este grupo.")
    return redirect("clases:group_books_index", group_id=group_id)


# =============================================================================
# ELEGIR Y ORDENAR LOS ELEMENTOS DE UN LIBRO PARA UN GRUPO
# =============================================================================


@login_required
@user_passes_test(is_staff)
def group_book_items(request, pk):
    """Qué elementos del libro se ven con este grupo, y en qué orden."""
    group_book = _libro_del_profesor(request, pk)
    filas = libros_de_grupo.enumerar(group_book)
    vistos, total = libros_de_grupo.progreso(group_book)

    return render(
        request,
        "clases/group_books/items.html",
        {
            "group": group_book.group,
            "group_book": group_book,
            "filas": filas,
            "vistos": vistos,
            "total": total,
            "ultima": len(filas) - 1,
        },
    )


def _fila_de(group_book, tipo_id, objeto_id):
    """La fila de `enumerar` que corresponde a un medio concreto."""
    for fila in libros_de_grupo.enumerar(group_book):
        if fila["tipo"].pk == tipo_id and fila["objeto"].pk == objeto_id:
            return fila
    return None


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def group_book_item_toggle(request, pk):
    """Cambia una propiedad de un elemento para este grupo. Devuelve su fila.

    `campo` es `incluido`, `a_casa` o `visto`. Los tres son reversibles: en
    clase se dan toques por error, y sin vuelta atrás se deja de marcar.
    """
    group_book = _libro_del_profesor(request, pk)
    tipo_id = int(request.POST.get("content_type"))
    objeto_id = int(request.POST.get("object_id"))
    campo = request.POST.get("campo")

    fila = _fila_de(group_book, tipo_id, objeto_id)
    if fila is None:
        return render(request, "clases/group_books/partials/fila.html", {})

    item = fila["item"]
    if campo == "incluido":
        valor = not (item.incluido if item else True)
        cambios = {"incluido": valor}
    elif campo == "a_casa":
        valor = not (item.a_casa if item else False)
        cambios = {"a_casa": valor}
    elif campo == "visto":
        ya = item is not None and item.estado == GroupBookItem.VISTO
        cambios = {"estado": GroupBookItem.PENDIENTE if ya else GroupBookItem.VISTO}
    else:
        cambios = {}

    if cambios:
        libros_de_grupo.excepcion(
            group_book, fila["objeto"], capitulo=fila["capitulo"], **cambios
        )

    fila = _fila_de(group_book, tipo_id, objeto_id)
    vistos, total = libros_de_grupo.progreso(group_book)
    return render(
        request,
        "clases/group_books/partials/fila.html",
        {
            "group_book": group_book,
            "fila": fila,
            # `oob` hace que la respuesta arrastre también el contador: sin esto
            # la fila decía "visto" y el contador seguía en cero.
            "oob": True,
            "vistos": vistos,
            "total": total,
        },
    )


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def group_book_item_move(request, pk):
    """Sube o baja un elemento en el orden de ESTE grupo.

    Botones en vez de arrastrar: la clase se da con el iPad, y arrastrar en
    táctil dentro de una lista larga con scroll pelea con el propio scroll.
    """
    group_book = _libro_del_profesor(request, pk)
    tipo_id = int(request.POST.get("content_type"))
    objeto_id = int(request.POST.get("object_id"))
    delta = -1 if request.POST.get("hacia") == "arriba" else 1

    claves = [(f["tipo"].pk, f["objeto"].pk) for f in libros_de_grupo.enumerar(group_book)]
    actual = (tipo_id, objeto_id)
    if actual in claves:
        i = claves.index(actual)
        j = i + delta
        if 0 <= j < len(claves):
            claves[i], claves[j] = claves[j], claves[i]
            libros_de_grupo.recolocar(group_book, claves)

    return redirect("clases:group_book_items", pk=group_book.pk)


# =============================================================================
# PREPARAR LA SESIÓN
# =============================================================================


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def class_session_prepare(request, pk):
    """Mete en la sesión el siguiente pendiente de cada sección elegida."""
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    secciones = request.POST.getlist("secciones") or None
    creados = libros_de_grupo.preparar_sesion(session, secciones)

    if creados:
        messages.success(
            request,
            f"{len(creados)} elemento{'s' if len(creados) != 1 else ''} añadido"
            f"{'s' if len(creados) != 1 else ''} desde los libros del grupo.",
        )
    else:
        messages.info(
            request,
            "No había nada nuevo que proponer: o los libros están al día, o ya estaban en la sesión.",
        )
    return redirect("clases:class_session_edit", pk=session.pk)


@login_required
@user_passes_test(is_staff)
def class_session_prepare_preview(request, pk):
    """Qué metería el botón de preparar, antes de pulsarlo."""
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    return render(
        request,
        "clases/class_sessions/partials/preparar.html",
        {
            "session": session,
            "propuesta": libros_de_grupo.previsualizar_sesion(session.group, session=session),
            "secciones": GroupBook.SECCIONES,
        },
    )


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def class_session_item_visto(request, pk):
    """Da por visto un elemento de la clase, y avanza el libro del que salió."""
    item = get_object_or_404(
        ClassSessionItem.objects.select_related("session"), pk=pk, session__teacher=request.user
    )
    libros_de_grupo.marcar_visto(item, visto=not item.visto)
    return render(
        request,
        "clases/class_sessions/partials/visto.html",
        {"item": item},
    )


@login_required
@user_passes_test(is_staff)
def class_session_preview_content(request, pk):
    """Enseña un elemento ANTES de meterlo en la clase.

    Es el ojo de la vista previa: sirve para decidir qué entra y qué no sin
    tener que añadirlo primero y quitarlo después.

    Se monta un `ClassSessionItem` **sin guardar** y se pinta con
    `render_item_content`, el mismo camino que usa la clase. Así lo que se ve
    aquí es exactamente lo que se verá luego; con un renderizador aparte las dos
    vistas acabarían discrepando.
    """

    from clases.views import render_item_content

    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    tipo = get_object_or_404(ContentType, pk=request.GET.get("content_type"))
    borrador = ClassSessionItem(
        session=session,
        content_type=tipo,
        object_id=request.GET.get("object_id"),
    )
    if borrador.content_object is None:
        return render(request, "clases/class_sessions/partials/sin_contenido.html", {})
    return render_item_content(request, borrador)


# =============================================================================
# PLANTILLAS PARA ESCRIBIR
# =============================================================================

# La página del sitio que las guarda. Es una página de Wagtail normal, así que
# las plantillas se editan desde el CMS y aquí no hay nada que tocar cuando se
# añade una. Si algún día se mueve, esto es lo único que cambia.
SLUG_PLANTILLAS = "plantillas-para-escribir"


@login_required
@user_passes_test(is_staff)
def plantillas(request):
    """Las plantillas de escritura, para abrirlas en mitad de una clase.

    Salen de la página del sitio con `material_de`, el mismo recorrido que usan
    los libros: lo que esté puesto en esa página aparece aquí sin tocar código.

    **Con vuelta atrás a propósito.** Si esa página no da material practicable
    —porque enlaza a otras páginas en vez de llevar los ficheros dentro—, se
    enseña la página entera en un iframe. Prefiero eso a una rejilla vacía sin
    explicación: el profesor está delante de la clase y necesita la plantilla,
    no un diagnóstico.
    """
    from my_library.libros import material_de
    from wagtail.models import Page

    pagina = Page.objects.filter(slug=SLUG_PLANTILLAS).live().first()
    if pagina is None:
        return render(
            request,
            "clases/class_sessions/partials/plantillas.html",
            {"pagina": None, "medios": []},
        )

    concreta = pagina.specific
    medios = []
    for objeto in material_de(concreta):
        icono, titulo, tipo = libros_de_grupo.describir(objeto)
        medios.append(
            {
                "icono": icono,
                "titulo": titulo,
                "tipo": tipo,
                "tipo_pk": ContentType.objects.get_for_model(objeto).pk,
                "pk": objeto.pk,
                "url": getattr(getattr(objeto, "file", None), "url", "")
                or getattr(objeto, "url", ""),
            }
        )

    return render(
        request,
        "clases/class_sessions/partials/plantillas.html",
        {"pagina": concreta, "medios": medios},
    )


@login_required
@user_passes_test(is_staff)
def plantilla_contenido(request):
    """Una plantilla concreta, con el visor de la clase.

    Va por `render_item_content` como todo lo demás, sobre un
    `ClassSessionItem` sin guardar y sin sesión: aquí solo se le piden el tipo y
    el objeto. Así la plantilla se ve con el mismo visor de PDF que el resto de
    la clase, en vez de con el del navegador.

    No es solo estética. Un PDF dentro de un `iframe` se queda con el foco del
    teclado, y entonces `Escape` no llega a la página: el profesor se quedaba
    encerrado en la plantilla sin poder volver a la clase.
    """
    from clases.views import render_item_content

    tipo = get_object_or_404(ContentType, pk=request.GET.get("content_type"))
    borrador = ClassSessionItem(
        content_type=tipo,
        object_id=request.GET.get("object_id"),
    )
    if borrador.content_object is None:
        return render(request, "clases/class_sessions/partials/sin_contenido.html", {})
    return render_item_content(request, borrador)
