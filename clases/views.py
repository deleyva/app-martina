from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from django.contrib.contenttypes.models import ContentType
import json

from .models import Group, GroupLibraryItem, ClassSession, ClassSessionItem


# Helper function to check if user is staff
def is_staff(user):
    return user.is_staff


# =============================================================================
# VISTAS DE BIBLIOTECA DE GRUPO
# =============================================================================


@login_required
@user_passes_test(is_staff)
def group_library_index(request, group_id):
    """
    Vista principal de la biblioteca del grupo.
    TINY VIEW: solo orquesta y renderiza.
    Solo profesores del grupo pueden acceder.
    """
    group = get_object_or_404(Group, pk=group_id)
    
    # Verificar que el profesor pertenece a este grupo
    if not group.teachers.filter(pk=request.user.pk).exists():
        messages.error(request, "No tienes permiso para acceder a la biblioteca de este grupo.")
        return redirect("evaluations:evaluation_item_list")
    
    items = GroupLibraryItem.objects.filter(group=group)
    
    return render(
        request,
        "clases/group_library/index.html",
        {
            "group": group,
            "items": items,
            "total_items": items.count(),
        },
    )


@login_required
@user_passes_test(is_staff)
def group_library_add(request, group_id):
    """
    Endpoint HTMX para añadir item a biblioteca de grupo.
    TINY VIEW: lógica en el modelo (FAT MODEL).
    """
    if request.method == "POST":
        group = get_object_or_404(Group, pk=group_id)
        
        # Verificar que el profesor pertenece a este grupo
        if not group.teachers.filter(pk=request.user.pk).exists():
            return HttpResponse("No autorizado", status=403)
        
        content_type_id = request.POST.get("content_type_id")
        object_id = request.POST.get("object_id")
        notes = request.POST.get("notes", "")

        content_type = get_object_or_404(ContentType, id=content_type_id)
        content_object = content_type.get_object_for_this_type(pk=object_id)

        # Lógica en el modelo (FAT MODEL)
        item, created = GroupLibraryItem.add_to_library(
            group=group,
            content_object=content_object,
            added_by=request.user,
            notes=notes
        )

        # Renderizar botón actualizado (HTMX swap)
        return render(
            request,
            "clases/group_library/partials/add_button.html",
            {
                "group": group,
                "content_object": content_object,
                "content_type": content_type,
                "in_library": True,
            },
        )

    return HttpResponse(status=405)


@login_required
@user_passes_test(is_staff)
def group_library_remove(request, group_id, pk):
    """
    Endpoint HTMX para quitar item de biblioteca de grupo por ID.
    TINY VIEW: solo elimina y renderiza.
    """
    group = get_object_or_404(Group, pk=group_id)
    
    # Verificar que el profesor pertenece a este grupo
    if not group.teachers.filter(pk=request.user.pk).exists():
        return HttpResponse("No autorizado", status=403)
    
    item = get_object_or_404(GroupLibraryItem, pk=pk, group=group)
    content_object = item.content_object
    content_type = item.content_type
    item.delete()

    # Renderizar botón actualizado (HTMX swap)
    return render(
        request,
        "clases/group_library/partials/add_button.html",
        {
            "group": group,
            "content_object": content_object,
            "content_type": content_type,
            "in_library": False,
        },
    )


@login_required
@user_passes_test(is_staff)
def group_library_remove_by_content(request, group_id):
    """
    Endpoint HTMX para quitar item de biblioteca de grupo por content_type y object_id.
    TINY VIEW: solo elimina y renderiza.
    """
    if request.method in ["POST", "DELETE"]:
        group = get_object_or_404(Group, pk=group_id)
        
        # Verificar que el profesor pertenece a este grupo
        if not group.teachers.filter(pk=request.user.pk).exists():
            return HttpResponse("No autorizado", status=403)
        
        content_type_id = request.POST.get("content_type_id")
        object_id = request.POST.get("object_id")

        content_type = get_object_or_404(ContentType, id=content_type_id)
        content_object = content_type.get_object_for_this_type(pk=object_id)

        # Eliminar si existe
        GroupLibraryItem.objects.filter(
            group=group,
            content_type=content_type,
            object_id=object_id,
        ).delete()

        # Renderizar botón actualizado (HTMX swap)
        return render(
            request,
            "clases/group_library/partials/add_button.html",
            {
                "group": group,
                "content_object": content_object,
                "content_type": content_type,
                "in_library": False,
            },
        )

    return HttpResponse(status=405)


# =============================================================================
# VISTAS DE SESIONES DE CLASE
# =============================================================================


@login_required
@user_passes_test(is_staff)
def class_session_list(request):
    """
    Lista de sesiones de clase del profesor.
    TINY VIEW: solo orquesta y renderiza.
    """
    # Obtener grupos del profesor
    groups = request.user.teaching_groups.all()
    
    # Obtener sesiones del profesor ordenadas
    sessions = ClassSession.objects.filter(teacher=request.user).select_related("group")
    
    return render(
        request,
        "clases/class_sessions/list.html",
        {
            "sessions": sessions,
            "groups": groups,
        },
    )


@login_required
@user_passes_test(is_staff)
def class_session_create(request):
    """
    Crear nueva sesión de clase.
    TINY VIEW: solo crea y redirige.
    """
    if request.method == "POST":
        group_id = request.POST.get("group")
        date = request.POST.get("date")
        title = request.POST.get("title")
        notes = request.POST.get("notes", "")
        
        group = get_object_or_404(Group, pk=group_id)
        
        # Verificar que el profesor pertenece a este grupo
        if not group.teachers.filter(pk=request.user.pk).exists():
            messages.error(request, "No tienes permiso para crear sesiones en este grupo.")
            return redirect("clases:class_session_list")
        
        # Crear sesión
        session = ClassSession.objects.create(
            teacher=request.user,
            group=group,
            date=date,
            title=title,
            notes=notes
        )
        
        messages.success(request, f"Sesión '{title}' creada exitosamente.")
        return redirect("clases:class_session_edit", pk=session.pk)
    
    # GET: Mostrar formulario
    groups = request.user.teaching_groups.all()
    return render(
        request,
        "clases/class_sessions/create.html",
        {"groups": groups},
    )


@login_required
@user_passes_test(is_staff)
def class_session_edit(request, pk):
    """
    Editar sesión de clase con drag & drop.
    TINY VIEW: solo renderiza.
    """
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    items = session.get_items_ordered()
    
    # Obtener elementos de la biblioteca del grupo para añadir
    library_items = GroupLibraryItem.objects.filter(group=session.group)
    
    return render(
        request,
        "clases/class_sessions/edit.html",
        {
            "session": session,
            "items": items,
            "library_items": library_items,
        },
    )


@login_required
@user_passes_test(is_staff)
def class_session_add_item(request, session_id):
    """
    Endpoint HTMX para añadir item a sesión.
    TINY VIEW: lógica en el modelo (FAT MODEL).
    """
    if request.method == "POST":
        session = get_object_or_404(ClassSession, pk=session_id, teacher=request.user)
        
        content_type_id = request.POST.get("content_type_id")
        object_id = request.POST.get("object_id")
        notes = request.POST.get("notes", "")
        
        content_type = get_object_or_404(ContentType, id=content_type_id)
        content_object = content_type.get_object_for_this_type(pk=object_id)
        
        # Lógica en el modelo (FAT MODEL)
        item = ClassSessionItem.add_to_session(
            session=session,
            content_object=content_object,
            notes=notes
        )
        
        # Renderizar item añadido (HTMX swap)
        return render(
            request,
            "clases/class_sessions/partials/session_item.html",
            {
                "item": item,
                "session": session,
            },
        )
    
    return HttpResponse(status=405)


@login_required
@user_passes_test(is_staff)
def class_session_remove_item(request, session_id, item_id):
    """
    Endpoint HTMX para quitar item de sesión.
    TINY VIEW: solo elimina.
    """
    session = get_object_or_404(ClassSession, pk=session_id, teacher=request.user)
    item = get_object_or_404(ClassSessionItem, pk=item_id, session=session)
    item.delete()
    
    return HttpResponse("")  # Empty response para swap outerHTML


@login_required
@user_passes_test(is_staff)
def class_session_reorder_items(request, session_id):
    """
    Endpoint HTMX para reordenar items con drag & drop.
    TINY VIEW: lógica en el modelo (FAT MODEL).
    """
    if request.method == "POST":
        session = get_object_or_404(ClassSession, pk=session_id, teacher=request.user)
        
        # Obtener IDs en el nuevo orden desde el POST
        item_ids_json = request.POST.get("item_ids", "[]")
        item_ids = json.loads(item_ids_json)
        
        # Lógica en el modelo (FAT MODEL)
        session.reorder_items(item_ids)
        
        # Devolver 204 No Content para que HTMX no reemplace nada
        return HttpResponse(status=204)
    
    return HttpResponse(status=405)


@login_required
@user_passes_test(is_staff)
def class_session_delete(request, pk):
    """
    Eliminar sesión de clase.
    TINY VIEW: solo elimina y redirige.
    """
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    title = session.title
    session.delete()
    
    messages.success(request, f"Sesión '{title}' eliminada exitosamente.")
    return redirect("clases:class_session_list")


# ============================================================================
# VISTAS DE BIBLIOTECA MÚLTIPLE (Personal + Grupos)
# ============================================================================

@require_http_methods(["POST"])
@login_required
@user_passes_test(is_staff, login_url="/accounts/login/", redirect_field_name=None)
def add_to_multiple_libraries(request):
    """
    Añade un recurso a múltiples bibliotecas (personal y/o grupos).
    TINY VIEW: orquesta y delega al modelo.
    """
    from my_library.models import LibraryItem
    
    content_type_id = request.POST.get("content_type_id")
    object_id = request.POST.get("object_id")
    personal_library = request.POST.get("personal_library") == "true"
    group_ids = request.POST.getlist("group_ids")
    
    # Validar parámetros
    if not content_type_id or not object_id:
        return HttpResponse("Error: Parámetros inválidos", status=400)
    
    content_type = get_object_or_404(ContentType, pk=content_type_id)
    model_class = content_type.model_class()
    content_object = get_object_or_404(model_class, pk=object_id)
    
    added_count = 0
    
    # Añadir a biblioteca personal
    if personal_library:
        item, created = LibraryItem.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=object_id,
        )
        if created:
            added_count += 1
    
    # Añadir a bibliotecas de grupo
    for group_id in group_ids:
        group = get_object_or_404(Group, pk=group_id)
        
        # Verificar que el profesor pertenece al grupo
        if not group.teachers.filter(pk=request.user.pk).exists():
            continue
        
        # Usar el método del modelo para añadir
        item, created = GroupLibraryItem.objects.get_or_create(
            group=group,
            content_type=content_type,
            object_id=object_id,
            defaults={"added_by": request.user}
        )
        if created:
            added_count += 1
    
    # Respuesta HTMX simple
    if added_count > 0:
        return HttpResponse(f"✓ Añadido a {added_count} biblioteca(s)", status=200)
    else:
        return HttpResponse("El recurso ya estaba en las bibliotecas seleccionadas", status=200)
