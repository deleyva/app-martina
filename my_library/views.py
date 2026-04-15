import json

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.contrib.contenttypes.models import ContentType
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from .models import LibraryItem


@login_required
def my_library_index(request):
    """
    Vista principal de la biblioteca del usuario.
    TINY VIEW: solo orquesta y renderiza.
    """
    items = LibraryItem.objects.filter(user=request.user).select_related(
        "content_type", "source_page"
    )
    total_items = items.count()
    show_all = request.GET.get("show_all")
    has_more = False
    if not show_all and total_items > 6:
        items = items[:6]
        has_more = True
    return render(
        request,
        "my_library/index.html",
        {
            "items": items,
            "total_items": total_items,
            "has_more": has_more,
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
    level = request.POST.get("level")

    if level is not None and level.isdigit() and 0 <= int(level) <= 4:
        item.proficiency_level = int(level)
        item.save(update_fields=["proficiency_level"])

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
    if not item_pks:
        return render(request, "my_library/study_viewer.html", {
            "playlist_json": "[]",
            "total_items": 0,
            "first_item_pk": None,
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
