from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.contrib.contenttypes.models import ContentType
from .models import LibraryItem


@login_required
def my_library_index(request):
    """
    Vista principal de la biblioteca del usuario.
    TINY VIEW: solo orquesta y renderiza.
    """
    items = LibraryItem.objects.filter(user=request.user)
    return render(
        request,
        "my_library/index.html",
        {
            "items": items,
            "total_items": items.count(),
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

        # Lógica en el modelo (FAT MODEL)
        item, created = LibraryItem.add_to_library(request.user, content_object)

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

    return render(
        request,
        "my_library/viewer.html",
        {
            "item": item,
            "documents": documents,
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
    
    if level and level.isdigit() and 1 <= int(level) <= 4:
        item.proficiency_level = int(level)
        item.save(update_fields=["proficiency_level"])
    
    # Renderizar partial con las estrellas actualizadas
    return render(
        request,
        "my_library/partials/proficiency_stars.html",
        {"item": item}
    )
