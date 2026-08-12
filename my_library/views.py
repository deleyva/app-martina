import json
import uuid

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.db.models import Count
from .models import LibraryDeck, LibraryItem, ReviewLog, SharedNote
from . import facets
from .session import (
    TAMANO_SESION_POR_DEFECTO,
    construir_sesion,
    facetas_disponibles,
    filtrar_por_facetas,
)


def _parse_uuid(raw):
    """UUID del cliente, o None. Un valor mal formado no debe reventar el POST."""
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError, TypeError):
        return None


def _parse_level(raw):
    """Nivel de proficiency 0-4, o None si no es válido."""
    if raw is not None and str(raw).isdigit() and 0 <= int(raw) <= 4:
        return int(raw)
    return None


@login_required
def my_library_index(request):
    """
    Vista principal de la biblioteca del usuario.
    TINY VIEW: solo orquesta y renderiza.
    """
    all_items = LibraryItem.objects.filter(user=request.user).select_related(
        "content_type", "source_page"
    ).prefetch_related("tags")
    total_items = all_items.count()
    show_all = request.GET.get("show_all")
    has_more = False
    items = all_items
    if not show_all and total_items > 6:
        items = all_items[:6]
        has_more = True

    decks_with_counts = _build_decks_with_counts(request.user, all_items)

    return render(
        request,
        "my_library/index.html",
        {
            "items": items,
            "total_items": total_items,
            "has_more": has_more,
            "decks_with_counts": decks_with_counts,
        },
    )


@login_required
def add_to_library(request):
    """
    Endpoint HTMX para añadir item a biblioteca.
    TINY VIEW: lógica en el modelo (FAT MODEL).
    """
    if request.method == "POST":
        content_type_id = request.POST.get("content_type_id")
        object_id = request.POST.get("object_id")

        content_type = get_object_or_404(ContentType, id=content_type_id)
        content_object = content_type.get_object_for_this_type(pk=object_id)

        try:
            # Lógica en el modelo (FAT MODEL)
            source_page_id = request.POST.get("source_page_id")
            LibraryItem.add_to_library(
                request.user, content_object, source_page_id=source_page_id
            )

            # Renderizar botón actualizado (HTMX swap)
            return render(
                request,
                "my_library/partials/add_button.html",
                {
                    "content_object": content_object,
                    "content_type": content_type,
                    "in_library": True,
                    "user": request.user,
                },
            )
        except ValueError as e:
            # ScorePages no están permitidas en biblioteca personal
            return HttpResponse(
                f'<span class="text-error text-sm">{str(e)}</span>',
                status=400,
            )

    return HttpResponse(status=405)


@login_required
def remove_from_library(request, pk):
    """
    Endpoint HTMX para quitar item de biblioteca por ID.
    TINY VIEW: solo elimina y renderiza.
    """
    item = get_object_or_404(LibraryItem, pk=pk, user=request.user)
    content_object = item.content_object
    content_type = item.content_type
    item.delete()

    # Renderizar botón actualizado (HTMX swap)
    return render(
        request,
        "my_library/partials/add_button.html",
        {
            "content_object": content_object,
            "content_type": content_type,
            "in_library": False,
            "user": request.user,
        },
    )


@login_required
def remove_by_content(request):
    """
    Endpoint HTMX para quitar item de biblioteca por content_type y object_id.
    TINY VIEW: solo elimina y renderiza.
    """
    if request.method in ["POST", "DELETE"]:
        content_type_id = request.POST.get("content_type_id")
        object_id = request.POST.get("object_id")

        content_type = get_object_or_404(ContentType, id=content_type_id)
        content_object = content_type.get_object_for_this_type(pk=object_id)

        # Eliminar si existe
        LibraryItem.objects.filter(
            user=request.user,
            content_type=content_type,
            object_id=object_id,
        ).delete()

        # Renderizar botón actualizado (HTMX swap)
        return render(
            request,
            "my_library/partials/add_button.html",
            {
                "content_object": content_object,
                "content_type": content_type,
                "in_library": False,
                "user": request.user,
            },
        )

    return HttpResponse(status=405)


@login_required
def view_library_item(request, pk):
    """
    Vista fullscreen para ver un item de la biblioteca.
    TINY VIEW: lógica de obtención de documentos en el modelo (FAT MODEL).
    """
    item = get_object_or_404(LibraryItem, pk=pk, user=request.user)

    # Lógica en el modelo (FAT MODEL)
    item.mark_as_viewed()
    documents = item.get_documents()
    score_media = item.get_related_scorepage_media()

    return render(
        request,
        "my_library/viewer.html",
        {
            "item": item,
            "documents": documents,
            "score_media": score_media,
        },
    )


@login_required
def view_content_object(request, content_type_id, object_id):
    content_type = get_object_or_404(ContentType, pk=content_type_id)
    model_class = content_type.model_class()
    if model_class is None:
        return HttpResponse(status=404)

    content_object = get_object_or_404(model_class, pk=object_id)

    item = LibraryItem(
        user=request.user,
        content_type=content_type,
        object_id=content_object.pk,
    )

    back_url = request.GET.get("back")
    if back_url and not url_has_allowed_host_and_scheme(
        back_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        back_url = None

    documents = item.get_documents()
    score_media = item.get_related_scorepage_media()

    return render(
        request,
        "my_library/viewer.html",
        {
            "item": item,
            "documents": documents,
            "score_media": score_media,
            "back_url": back_url,
        },
    )


@login_required
def update_proficiency(request, pk):
    """
    Actualizar nivel de conocimiento de un item (via HTMX).
    TINY VIEW: solo actualiza y renderiza.
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    item = get_object_or_404(LibraryItem, pk=pk, user=request.user)
    level = _parse_level(request.POST.get("level"))

    if level is not None:
        before = item.proficiency_level
        item.proficiency_level = level
        item.save(update_fields=["proficiency_level"])
        # Valorar desde el índice no es práctica: queda marcado como 'manual'
        # para que un futuro planificador pueda descartarlo.
        ReviewLog.log(
            item,
            source=ReviewLog.SOURCE_MANUAL,
            proficiency_before=before,
            proficiency_after=level,
        )

    # Renderizar partial con el slider actualizado
    response = render(
        request, "my_library/partials/proficiency_slider.html", {"item": item}
    )

    # Enviar evento HX-Trigger para que el cliente pueda reordenar la lista
    response["HX-Trigger"] = json.dumps(
        {
            "proficiencyUpdated": {
                "itemId": str(item.pk),
                "newLevel": item.proficiency_level,
            }
        }
    )

    return response


@login_required
@require_POST
def update_notes(request, pk):
    """Guarda las notas de práctica de un item.

    Es el camino de escritura del caso 'vi el vídeo una vez y apunté qué hay
    que hacer': después basta con leer la nota, sin volver a verlo.
    """
    item = get_object_or_404(LibraryItem, pk=pk, user=request.user)
    item.notes = request.POST.get("notes", "").strip()
    item.save(update_fields=["notes"])
    return HttpResponse(status=204)


@staff_member_required
@require_POST
def update_shared_note(request, pk):
    """Guarda la nota docente de un contenido. Solo profesorado.

    Se guarda contra el CONTENIDO, no contra el item de biblioteca: la escribe
    quien enseña y la ve todo el que estudie ese material, tenga o no el
    elemento en su propia biblioteca.
    """
    item = get_object_or_404(LibraryItem, pk=pk)
    if item.content_object is None:
        return HttpResponse(status=404)

    body = request.POST.get("body", "").strip()
    content_type = ContentType.objects.get_for_model(item.content_object)

    if body:
        SharedNote.objects.update_or_create(
            content_type=content_type,
            object_id=item.content_object.pk,
            defaults={"body": body, "author": request.user},
        )
    else:
        # Vaciarla es borrarla: no dejamos filas vacías por el camino.
        SharedNote.objects.filter(
            content_type=content_type, object_id=item.content_object.pk
        ).delete()

    return HttpResponse(status=204)


@staff_member_required
@require_POST
def update_item_title(request, pk):
    """
    Actualizar título del contenido subyacente (Document, Image, Embed).
    Solo para admin. HTMX endpoint.
    """
    item = get_object_or_404(LibraryItem, pk=pk)
    new_title = request.POST.get("title", "").strip()

    if not new_title:
        return HttpResponse(status=400)

    obj = item.content_object
    if obj and hasattr(obj, "title"):
        obj.title = new_title
        obj.save()
    elif obj and hasattr(obj, "name"):
        obj.name = new_title
        obj.save()

    return render(
        request,
        "my_library/partials/item_title.html",
        {"item": item, "is_admin": True},
    )


@staff_member_required
def suggest_tags(request):
    """
    Endpoint JSON para autocompletado de tags.
    Devuelve tags de taggit + MusicTag que coincidan con el query.
    """
    from taggit.models import Tag as TaggitTag
    from cms.models import MusicTag

    q = request.GET.get("q", "").strip().lower()
    if len(q) < 1:
        return JsonResponse([], safe=False)

    # Combinar tags de ambos sistemas
    taggit_tags = list(
        TaggitTag.objects.filter(name__icontains=q)
        .values_list("name", flat=True)
        .order_by("name")[:15]
    )
    music_tags = list(
        MusicTag.objects.filter(name__icontains=q)
        .values_list("name", flat=True)
        .order_by("name")[:15]
    )

    # Unir y deduplicar, mantener orden
    seen = set()
    combined = []
    for tag in taggit_tags + music_tags:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            combined.append(tag)

    return JsonResponse(combined[:20], safe=False)


@staff_member_required
@require_POST
def update_item_tags(request, pk):
    """
    Actualizar tags del contenido subyacente (Document, Image).
    Solo para admin. HTMX endpoint.
    """
    item = get_object_or_404(LibraryItem, pk=pk)
    tags_str = request.POST.get("tags", "").strip()
    tag_names = [t.strip() for t in tags_str.split(",") if t.strip()]

    obj = item.content_object
    if obj and hasattr(obj, "tags"):
        # Document/Image: tags en el content_object
        obj.tags.clear()
        for tag_name in tag_names:
            obj.tags.add(tag_name)
    else:
        # Embed u otro sin tags: tags en el LibraryItem
        item.tags.clear()
        for tag_name in tag_names:
            item.tags.add(tag_name)

    return render(
        request,
        "my_library/partials/item_tags.html",
        {"item": item, "is_admin": True},
    )


@login_required
def study_session_view(request):
    """Renderiza study_viewer.html con la playlist de items."""
    item_pks = [
        int(pk)
        for pk in request.GET.get("items", "").split(",")
        if pk.strip().isdigit()
    ]
    # Mazo de origen, si la sesión viene de uno. Se propaga a cada ReviewLog.
    deck_pk_raw = request.GET.get("deck", "")
    deck_pk = int(deck_pk_raw) if deck_pk_raw.isdigit() else ""

    if not item_pks:
        return render(request, "my_library/study_viewer.html", {
            "playlist_json": "[]",
            "total_items": 0,
            "first_item_pk": None,
            "deck_pk": deck_pk,
        })

    items = LibraryItem.objects.filter(pk__in=item_pks, user=request.user)
    items_by_pk = {item.pk: item for item in items}
    ordered_items = [items_by_pk[pk] for pk in item_pks if pk in items_by_pk]
    playlist = [
        {
            "pk": item.pk,
            "title": item.get_content_title(),
            "type": item.get_content_type_name(),
        }
        for item in ordered_items
    ]
    return render(request, "my_library/study_viewer.html", {
        "playlist_json": json.dumps(playlist),
        "total_items": len(playlist),
        "first_item_pk": playlist[0]["pk"] if playlist else None,
        "deck_pk": deck_pk,
    })


@login_required
def study_item_content(request, pk):
    """Devuelve el HTML del viewer para un item (sin wrapper)."""
    item = get_object_or_404(LibraryItem, pk=pk, user=request.user)
    documents = item.get_documents()
    score_media = item.get_related_scorepage_media()
    return render(request, "my_library/partials/study_item_content.html", {
        "item": item,
        "documents": documents,
        "score_media": score_media,
    })


@login_required
@require_POST
def mark_viewed(request, pk):
    """Marca un item como visto (incrementa times_viewed)."""
    item = get_object_or_404(LibraryItem, pk=pk, user=request.user)
    item.mark_as_viewed()
    return HttpResponse(status=204)


@login_required
@require_POST
def log_review(request, pk):
    """Registra un repaso completo desde el visor de estudio.

    Hace las tres cosas en un solo round trip: graba el ReviewLog, actualiza
    el nivel y marca el item como visto. El ReviewLog es el objetivo; los
    otros dos son los contadores que ya existían.
    """
    item = get_object_or_404(LibraryItem, pk=pk, user=request.user)

    before = item.proficiency_level
    after = _parse_level(request.POST.get("level"))
    if after is not None:
        item.proficiency_level = after
        item.save(update_fields=["proficiency_level"])

    item.mark_as_viewed()

    duration_raw = request.POST.get("duration_seconds", "")
    duration_seconds = int(duration_raw) if str(duration_raw).isdigit() else None

    deck = None
    deck_pk = request.POST.get("deck", "")
    if str(deck_pk).isdigit():
        deck = LibraryDeck.objects.filter(pk=int(deck_pk), user=request.user).first()

    ReviewLog.log(
        item,
        source=ReviewLog.SOURCE_STUDY,
        proficiency_before=before,
        proficiency_after=after,
        duration_seconds=duration_seconds,
        session_uuid=_parse_uuid(request.POST.get("session_uuid")),
        deck=deck,
    )

    return HttpResponse(status=204)


@staff_member_required
def manage_tags(request):
    """Página de gestión de taggit tags con conteo de uso."""
    from taggit.models import Tag

    tags = Tag.objects.annotate(
        usage_count=Count("taggit_taggeditem_items")
    ).order_by("name")
    return render(request, "my_library/manage_tags.html", {"tags": tags})


@staff_member_required
@require_POST
def merge_tags(request):
    """Fusiona tags seleccionados en un tag objetivo.
    Uses atomic transaction + bulk update to prevent data loss.
    """
    from taggit.models import Tag, TaggedItem
    from django.db import transaction

    source_pks = [int(pk) for pk in request.POST.getlist("source_pks") if pk.isdigit()]
    target_pk_str = request.POST.get("target_pk", "")
    if not target_pk_str.isdigit():
        messages.error(request, "Tag objetivo no válido.")
        return redirect("my_library:manage_tags")

    target_pk = int(target_pk_str)
    target = get_object_or_404(Tag, pk=target_pk)
    sources = Tag.objects.filter(pk__in=source_pks).exclude(pk=target_pk)

    merged_count = 0
    with transaction.atomic():
        for source in sources:
            # Snapshot all tagged items for this source into a list
            # to avoid queryset re-evaluation during mutation
            tagged_items = list(TaggedItem.objects.filter(tag=source))
            for item in tagged_items:
                exists = TaggedItem.objects.filter(
                    tag=target, content_type=item.content_type, object_id=item.object_id
                ).exists()
                if not exists:
                    item.tag = target
                    item.save()
                else:
                    item.delete()

            # Verify all items moved before deleting source tag
            remaining = TaggedItem.objects.filter(tag=source).count()
            if remaining > 0:
                raise RuntimeError(
                    f"Merge safety check failed: {remaining} items still on "
                    f'"{source.name}" after reassignment. Aborting.'
                )
            source.delete()
            merged_count += 1

    if merged_count:
        messages.success(
            request,
            f"{merged_count} tag(s) fusionado(s) en \"{target.name}\".",
        )
    else:
        messages.warning(request, "No se fusionó ningún tag.")

    return redirect("my_library:manage_tags")


# === Deck CRUD ===


@login_required
@require_POST
def create_deck(request):
    """Create a new deck from active tag filters. HTMX endpoint."""
    name = request.POST.get("name", "").strip()
    tags_str = request.POST.get("tags", "").strip()

    if not name or not tags_str:
        return HttpResponse(
            '<span class="text-error text-sm">Nombre y tags son obligatorios.</span>',
            status=400,
        )

    tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]
    if not tag_list:
        return HttpResponse(
            '<span class="text-error text-sm">Selecciona al menos un tag.</span>',
            status=400,
        )

    deck, created = LibraryDeck.objects.get_or_create(
        user=request.user,
        name=name,
        defaults={"tags_json": json.dumps(tag_list)},
    )
    if not created:
        return HttpResponse(
            '<span class="text-error text-sm">Ya existe un mazo con ese nombre.</span>',
            status=400,
        )

    # Return updated deck panel
    return _render_deck_panel(request)


@login_required
@require_POST
def delete_deck(request, pk):
    """Delete a deck. HTMX endpoint."""
    deck = get_object_or_404(LibraryDeck, pk=pk, user=request.user)
    deck.delete()
    return _render_deck_panel(request)


@login_required
@require_POST
def rename_deck(request, pk):
    """Rename a deck. HTMX endpoint."""
    deck = get_object_or_404(LibraryDeck, pk=pk, user=request.user)
    new_name = request.POST.get("name", "").strip()
    if not new_name:
        return HttpResponse(status=400)

    # Check unique constraint
    if LibraryDeck.objects.filter(user=request.user, name=new_name).exclude(pk=pk).exists():
        return HttpResponse(
            '<span class="text-error text-sm">Ya existe un mazo con ese nombre.</span>',
            status=400,
        )

    deck.name = new_name
    deck.save(update_fields=["name"])
    return _render_deck_panel(request)


def _seleccion_de(request):
    """Lee la selección de facetas de la query: `?instrumento=guitarra&...`."""
    seleccion = {}
    for faceta in facets.FACETAS_DE_FILTRO:
        valores = [v for v in request.GET.getlist(faceta) if v.strip()]
        if valores:
            seleccion[faceta] = valores
    return seleccion


def _items_del_usuario(user):
    return LibraryItem.objects.filter(user=user).select_related(
        "content_type", "source_page"
    ).prefetch_related("tags")


@login_required
def session_start(request):
    """Selector para arrancar una sesión: instrumento, concepto, estilo…

    Es la petición original: "digo el instrumento y algún concepto y que me
    filtre lo que tengo para repasar". Imposible hasta tener facetas, porque
    nada decía qué etiqueta ERA un instrumento.
    """
    items = list(_items_del_usuario(request.user))
    seleccion = _seleccion_de(request)

    # Se arma aquí con el flag `seleccionado` ya resuelto: mirar si un valor
    # está en un dict-de-conjuntos no se puede hacer en una plantilla Django
    # sin inventarse un filtro.
    facetas_ui = [
        {
            "nombre": faceta,
            "valores": [
                {
                    "valor": valor,
                    "cuantos": cuantos,
                    "seleccionado": valor in seleccion.get(faceta, []),
                }
                for valor, cuantos in valores
            ],
        }
        for faceta, valores in facetas_disponibles(items).items()
    ]

    return render(
        request,
        "my_library/session_start.html",
        {
            "facetas": facetas_ui,
            "total_biblioteca": len(items),
            "tamano_sesion": TAMANO_SESION_POR_DEFECTO,
            **_resumen_seleccion(items, seleccion),
        },
    )


def _resumen_seleccion(items, seleccion):
    coincidencias = filtrar_por_facetas(items, seleccion)
    sesion = construir_sesion(coincidencias, tamano=TAMANO_SESION_POR_DEFECTO)
    return {
        "coincidencias": len(coincidencias),
        "sesion": sesion,
        "hay_seleccion": bool(seleccion),
    }


@login_required
def session_count(request):
    """Recuento en vivo mientras se eligen facetas. Endpoint HTMX."""
    items = list(_items_del_usuario(request.user))
    return render(
        request,
        "my_library/partials/session_count.html",
        {
            "tamano_sesion": TAMANO_SESION_POR_DEFECTO,
            **_resumen_seleccion(items, _seleccion_de(request)),
        },
    )


@login_required
def session_launch(request):
    """Construye la sesión con las facetas elegidas y abre el visor."""
    items = list(_items_del_usuario(request.user))
    seleccion = _seleccion_de(request)

    coincidencias = filtrar_por_facetas(items, seleccion)
    if not coincidencias:
        messages.warning(request, "No hay elementos que casen con esa selección.")
        return redirect(f"{reverse('my_library:session_start')}?{request.GET.urlencode()}")

    tamano_raw = request.GET.get("size", "")
    tamano = int(tamano_raw) if tamano_raw.isdigit() else TAMANO_SESION_POR_DEFECTO
    sesion = construir_sesion(coincidencias, tamano=tamano)

    items_param = ",".join(str(item.pk) for item in sesion)
    return redirect(f"{reverse('my_library:study_session')}?items={items_param}")


@login_required
def deck_study(request, pk):
    """Arranca una sesión acotada con los elementos del mazo.

    El mazo puede tener 200 elementos: la sesión sigue siendo del mismo tamaño.
    Qué entra y en qué orden lo decide `construir_sesion`.
    """
    deck = get_object_or_404(LibraryDeck, pk=pk, user=request.user)
    items_qs = LibraryItem.objects.filter(user=request.user).select_related(
        "content_type", "source_page"
    ).prefetch_related("tags")
    tag_map = LibraryDeck.build_tag_map(items_qs)
    pks = deck.get_matching_item_pks(tag_map)
    if not pks:
        messages.warning(request, f'El mazo "{deck.name}" no tiene elementos que coincidan.')
        return redirect("my_library:index")

    tamano_raw = request.GET.get("size", "")
    tamano = (
        int(tamano_raw) if tamano_raw.isdigit() else TAMANO_SESION_POR_DEFECTO
    )

    pks_del_mazo = set(pks)
    candidatos = [item for item in items_qs if item.pk in pks_del_mazo]
    sesion = construir_sesion(candidatos, tamano=tamano)

    items_param = ",".join(str(item.pk) for item in sesion)
    return redirect(
        f"{reverse('my_library:study_session')}?items={items_param}&deck={deck.pk}"
    )


def _build_decks_with_counts(user, items_qs):
    """Build deck list with matching item counts. Shared by index view and HTMX endpoints."""
    decks = LibraryDeck.objects.filter(user=user)
    if not decks.exists():
        return []
    tag_map = LibraryDeck.build_tag_map(items_qs)
    return [
        {
            "deck": deck,
            "tags": deck.get_tags(),
            "count": len(deck.get_matching_item_pks(tag_map)),
        }
        for deck in decks
    ]


def _render_deck_panel(request):
    """Helper: render the deck panel partial with fresh data."""
    all_items_qs = LibraryItem.objects.filter(user=request.user).select_related(
        "content_type", "source_page"
    ).prefetch_related("tags")
    decks_with_counts = _build_decks_with_counts(request.user, all_items_qs)
    html = render_to_string(
        "my_library/partials/deck_panel.html",
        {"decks_with_counts": decks_with_counts},
        request=request,
    )
    return HttpResponse(html)
