from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import redirect_to_login
from django.views.decorators.http import require_http_methods
from django.contrib.contenttypes.models import ContentType
import json

from .models import (
    Group,
    GroupLibraryItem,
    ClassSession,
    ClassSessionItem,
    Student,
    GroupInvitation,
    Enrollment,
)


# Helper function to check if user is staff
def is_staff(user):
    return user.is_staff


# =============================================================================
# INVITACIONES A GRUPOS
# =============================================================================


@require_http_methods(["GET"])
def group_join_by_invitation(request, token):
    """Procesar enlace de invitación y unir al usuario al grupo.

    TINY VIEW: delega en GroupInvitation (FAT MODEL) y muestra mensajes.
    """
    if not request.is_secure():
        absolute_url = request.build_absolute_uri()
        if absolute_url.startswith("http://"):
            absolute_url = "https://" + absolute_url.removeprefix("http://")
        return redirect(absolute_url)

    if not request.user.is_authenticated:
        return redirect_to_login(
            request.get_full_path(),
            login_url=reverse("account_login"),
        )

    invitation = get_object_or_404(GroupInvitation, token=token)
    _, status = invitation.accept_for_user(request.user)

    if status == "invalid":
        messages.error(request, "Este enlace de invitación ya no es válido.")
    elif status == "already_in_group":
        messages.info(
            request,
            f"Ya estás matriculado en el grupo {invitation.group}.",
        )
    elif status == "joined":
        messages.success(request, f"Te has unido al grupo {invitation.group}.")
    else:
        messages.error(
            request,
            "No se ha podido procesar la invitación. Contacta con tu profesor.",
        )

    return redirect("clases:class_session_list")


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
        messages.error(
            request, "No tienes permiso para acceder a la biblioteca de este grupo."
        )
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
            notes=notes,
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
def group_library_update_proficiency(request, group_id, pk):
    """Actualizar nivel de conocimiento del grupo para un item de biblioteca (via HTMX).

    TINY VIEW: solo actualiza y renderiza.
    """

    if request.method != "POST":
        return HttpResponse(status=405)

    group = get_object_or_404(Group, pk=group_id)

    # Verificar que el profesor pertenece a este grupo
    if not group.teachers.filter(pk=request.user.pk).exists():
        return HttpResponse("No autorizado", status=403)

    item = get_object_or_404(GroupLibraryItem, pk=pk, group=group)
    level = request.POST.get("level")

    if level and level.isdigit() and 1 <= int(level) <= 4:
        item.group_proficiency_level = int(level)
        item.save(update_fields=["group_proficiency_level"])

    return render(
        request,
        "clases/group_library/partials/group_proficiency_stars.html",
        {"item": item, "group": group},
    )


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST", "DELETE"])
def group_library_remove(request, group_id, pk):
    """
    Endpoint HTMX para quitar item de biblioteca de grupo por ID.
    TINY VIEW: solo elimina y renderiza.

    Si viene de la página de índice de biblioteca (hx-target apunta a un li),
    devuelve respuesta vacía para eliminar el elemento.
    Si viene de otro lugar, devuelve el botón actualizado.
    """
    group = get_object_or_404(Group, pk=group_id)

    # Verificar que el profesor pertenece a este grupo
    if not group.teachers.filter(pk=request.user.pk).exists():
        return HttpResponse("No autorizado", status=403)

    item = get_object_or_404(GroupLibraryItem, pk=pk, group=group)
    content_object = item.content_object
    content_type = item.content_type
    item.delete()

    # Si viene de la página de índice (el target es library-item-X), devolver vacío
    hx_target = request.headers.get("HX-Target", "")
    if hx_target.startswith("library-item-"):
        return HttpResponse("")

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
def class_session_list(request):
    """
    Lista de sesiones de clase.
    - Para profesores: muestra todas sus sesiones
    - Para estudiantes: muestra sesiones de sus grupos (multi-grupo)
    TINY VIEW: solo orquesta y renderiza.
    """
    user = request.user
    is_teacher = user.is_staff and hasattr(user, "teaching_groups")

    if is_teacher:
        # Profesor: ver todas sus sesiones
        groups = user.teaching_groups.all()
        sessions = ClassSession.objects.filter(teacher=user).select_related("group")
    else:
        # Estudiante: ver sesiones de todos sus grupos activos
        enrolled_groups = Group.objects.filter(
            enrollments__user=user, enrollments__is_active=True
        ).distinct()
        groups = list(enrolled_groups)
        sessions = ClassSession.objects.filter(
            group__in=enrolled_groups
        ).select_related("group", "teacher")

    return render(
        request,
        "clases/class_sessions/list.html",
        {
            "sessions": sessions,
            "groups": groups,
            "is_teacher": is_teacher,
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
            messages.error(
                request, "No tienes permiso para crear sesiones en este grupo."
            )
            return redirect("clases:class_session_list")

        # Crear sesión
        session = ClassSession.objects.create(
            teacher=request.user, group=group, date=date, title=title, notes=notes
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
def class_session_edit_details(request, pk):
    """
    Editar detalles de sesión (grupo, fecha, título, notas).
    TINY VIEW: actualiza datos básicos y redirige.
    """
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)

    if request.method == "POST":
        group_id = request.POST.get("group")
        date = request.POST.get("date")
        title = request.POST.get("title")
        notes = request.POST.get("notes", "")

        group = get_object_or_404(Group, pk=group_id)

        # Verificar que el profesor pertenece a este grupo
        if not group.teachers.filter(pk=request.user.pk).exists():
            messages.error(
                request, "No tienes permiso para asignar sesiones a este grupo."
            )
            return redirect("clases:class_session_list")

        # Actualizar sesión (FAT MODEL)
        session.group = group
        session.date = date
        session.title = title
        session.notes = notes
        session.save()

        messages.success(request, f"Sesión '{title}' actualizada exitosamente.")
        return redirect("clases:class_session_edit", pk=session.pk)

    # GET: Mostrar formulario de edición
    groups = request.user.teaching_groups.all()
    return render(
        request,
        "clases/class_sessions/edit_details.html",
        {
            "session": session,
            "groups": groups,
        },
    )


@login_required
def class_session_view(request, pk):
    """
    Ver sesión de clase (solo lectura).
    - Para profesores: pueden ver sus propias sesiones
    - Para estudiantes: pueden ver sesiones de sus grupos (multi-grupo)
    TINY VIEW: solo renderiza.
    """
    user = request.user
    is_teacher = user.is_staff and hasattr(user, "teaching_groups")

    if is_teacher:
        # Profesor: ver su propia sesión
        session = get_object_or_404(ClassSession, pk=pk, teacher=user)
    else:
        # Estudiante: ver sesión de cualquiera de sus grupos activos
        session = get_object_or_404(ClassSession, pk=pk)

        # Verificar que el estudiante está matriculado en el grupo de la sesión
        is_enrolled = Enrollment.objects.filter(
            user=user, group=session.group, is_active=True
        ).exists()

        if not is_enrolled:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("No tienes permiso para ver esta sesión.")

    items = session.get_items_ordered()

    return render(
        request,
        "clases/class_sessions/view.html",
        {
            "session": session,
            "items": items,
            "is_teacher": is_teacher,
        },
    )


@login_required
@user_passes_test(is_staff)
def class_session_edit(request, pk):
    """
    Editar sesión de clase con drag & drop.
    TINY VIEW: solo renderiza con paginación y filtros.
    """
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    items = session.get_items_ordered()

    # Parámetros de búsqueda y paginación para biblioteca
    search = request.GET.get("search", "")
    tag_filter = request.GET.get("tag", "")
    page_size = int(request.GET.get("page_size", 5))
    offset = int(request.GET.get("offset", 0))

    # Query base de biblioteca del grupo
    from django.db.models import Q
    from cms.models import ScorePage

    library_items = GroupLibraryItem.objects.filter(group=session.group)

    # Filtrar por búsqueda (título del contenido y tags)
    if search:
        # Obtener IDs de ScorePages que coinciden con la búsqueda
        matching_score_ids = (
            ScorePage.objects.filter(
                Q(title__icontains=search)
                | Q(tags__name__icontains=search)
                | Q(categories__name__icontains=search)
            )
            .values_list("pk", flat=True)
            .distinct()
        )

        # Obtener content_type de ScorePage
        from django.contrib.contenttypes.models import ContentType
        from wagtail.documents.models import Document
        from wagtail.images.models import Image

        scorepage_ct = ContentType.objects.get_for_model(ScorePage)
        document_ct = ContentType.objects.get_for_model(Document)
        image_ct = ContentType.objects.get_for_model(Image)

        # Buscar Documents e Images que coincidan con el título
        matching_doc_ids = Document.objects.filter(title__icontains=search).values_list(
            "pk", flat=True
        )

        matching_img_ids = Image.objects.filter(title__icontains=search).values_list(
            "pk", flat=True
        )

        # object_id es CharField en GenericForeignKey, convertir a strings
        matching_score_ids_str = [str(pk) for pk in matching_score_ids]
        matching_doc_ids_str = [str(pk) for pk in matching_doc_ids]
        matching_img_ids_str = [str(pk) for pk in matching_img_ids]

        # Filtrar library_items: por tipo/notas o por matches en contenido
        library_items = library_items.filter(
            Q(content_type__model__icontains=search)
            | Q(notes__icontains=search)
            | Q(content_type=scorepage_ct, object_id__in=matching_score_ids_str)
            | Q(content_type=document_ct, object_id__in=matching_doc_ids_str)
            | Q(content_type=image_ct, object_id__in=matching_img_ids_str)
        )

    # Ordenar: por fecha añadido (el contador de sesiones se muestra pero no ordena)
    library_items = library_items.order_by("-added_at")

    # Paginación
    total_library_items = library_items.count()
    library_items_page = library_items[offset : offset + page_size]
    has_more = total_library_items > (offset + page_size)
    next_offset = offset + page_size if has_more else None

    # Obtener todos los tags disponibles (de ScorePages en la biblioteca)
    # Para el filtro dropdown
    available_tags = set()
    for lib_item in library_items:
        tags = lib_item.get_related_tags()
        for tag in tags:
            available_tags.add(tag)

    context = {
        "session": session,
        "items": items,
        "library_items": library_items_page,
        "total_library_items": total_library_items,
        "has_more": has_more,
        "next_offset": next_offset,
        "page_size": page_size,
        "search": search,
        "tag_filter": tag_filter,
        "available_tags": sorted(
            available_tags, key=lambda t: t.name if hasattr(t, "name") else str(t)
        ),
    }

    # Si es petición HTMX, devolver solo las filas
    if request.headers.get("HX-Request"):
        return render(
            request,
            "clases/class_sessions/partials/library_rows.html",
            context,
        )

    # Si es petición normal, devolver template completo
    return render(
        request,
        "clases/class_sessions/edit.html",
        context,
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

        try:
            # Lógica en el modelo (FAT MODEL)
            item = ClassSessionItem.add_to_session(
                session=session, content_object=content_object, notes=notes
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
        except ValueError as e:
            # ScorePages no están permitidas en sesiones de clase
            return HttpResponse(
                f'<span class="text-error text-sm">{str(e)}</span>',
                status=400,
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
def get_item_session_count(request, group_id):
    """
    Endpoint HTMX para obtener el contador actualizado de sesiones de un item.
    Devuelve solo el número para innerHTML swap.
    """
    from django.contrib.contenttypes.models import ContentType

    content_type_id = request.GET.get("content_type_id")
    object_id = request.GET.get("object_id")

    # Verificar que el usuario tiene acceso al grupo
    group = get_object_or_404(Group, pk=group_id)
    if request.user not in group.teachers.all() and not request.user.is_staff:
        return HttpResponse("0")

    # Obtener content_type y contar sesiones
    content_type = get_object_or_404(ContentType, pk=content_type_id)
    count = GroupLibraryItem.get_session_count_for_object(
        group, content_type.get_object_for_this_type(pk=object_id)
    )

    return HttpResponse(str(count))


@login_required
@user_passes_test(is_staff)
def get_scorepage_total_count(request, group_id):
    """
    Endpoint HTMX para obtener el contador sumatorio de una ScorePage.
    Suma todos los elementos (PDFs, audios, imágenes, embeds) añadidos a sesiones.
    Devuelve solo el número para innerHTML swap.
    """
    library_item_id = request.GET.get("library_item_id")

    # Verificar que el usuario tiene acceso al grupo
    group = get_object_or_404(Group, pk=group_id)
    if request.user not in group.teachers.all() and not request.user.is_staff:
        return HttpResponse("0")

    # Obtener GroupLibraryItem y su contador sumatorio
    library_item = get_object_or_404(GroupLibraryItem, pk=library_item_id, group=group)
    count = library_item.get_scorepage_total_session_count()

    return HttpResponse(str(count))


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
def class_session_duplicate(request, pk):
    """
    Duplicar sesión de clase incluyendo todos sus items.
    TINY VIEW: duplica y redirige a edición.
    """
    original_session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)

    # Crear nueva sesión con datos copiados (FAT MODEL lógica en el modelo)
    new_session = ClassSession.objects.create(
        teacher=original_session.teacher,
        group=original_session.group,
        date=original_session.date,
        title=f"Copia de {original_session.title}",
        notes=original_session.notes,
        metadata=original_session.metadata.copy() if original_session.metadata else {},
    )

    # Duplicar todos los items de la sesión original
    for item in original_session.items.all():
        ClassSessionItem.objects.create(
            session=new_session,
            content_type=item.content_type,
            object_id=item.object_id,
            order=item.order,
            notes=item.notes,
        )

    messages.success(
        request,
        f"Sesión '{original_session.title}' duplicada exitosamente como '{new_session.title}'.",
    )

    # Redirigir a edición de detalles de la nueva sesión
    return redirect("clases:class_session_edit_details", pk=new_session.pk)


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
    Añade un recurso a múltiples bibliotecas (personal, grupos y/o estudiantes).
    TINY VIEW: orquesta y delega al modelo.
    """
    from my_library.models import LibraryItem

    content_type_id = request.POST.get("content_type_id")
    object_id = request.POST.get("object_id")
    personal_library = request.POST.get("personal_library") == "true"
    group_ids = request.POST.getlist("group_ids")
    student_ids = request.POST.getlist("student_ids")

    # Validar parámetros
    if not content_type_id or not object_id:
        return HttpResponse("Error: Parámetros inválidos", status=400)

    content_type = get_object_or_404(ContentType, pk=content_type_id)
    model_class = content_type.model_class()
    content_object = get_object_or_404(model_class, pk=object_id)

    added_count = 0
    already_exists_count = 0

    # Añadir a biblioteca personal del profesor
    if personal_library:
        item, created = LibraryItem.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=object_id,
        )
        if created:
            added_count += 1
        else:
            already_exists_count += 1

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
            defaults={"added_by": request.user},
        )
        if created:
            added_count += 1
        else:
            already_exists_count += 1

    # Añadir a bibliotecas personales de estudiantes
    for student_id in student_ids:
        student = get_object_or_404(Student, pk=student_id)

        # Verificar que el profesor pertenece al grupo del estudiante
        if not student.group.teachers.filter(pk=request.user.pk).exists():
            continue

        # Verificar que el estudiante tiene usuario asociado
        if not student.user:
            continue

        # Usar el método del modelo (FAT MODEL)
        item, created = LibraryItem.add_to_library(
            user=student.user, content_object=content_object
        )

        if created:
            added_count += 1
        else:
            already_exists_count += 1

    # Respuesta HTMX con detalles
    if added_count > 0:
        msg = f"✓ Añadido a {added_count} biblioteca(s)"
        if already_exists_count > 0:
            msg += f" ({already_exists_count} ya existía(n))"
        return HttpResponse(msg, status=200)
    else:
        return HttpResponse(
            "El recurso ya estaba en las bibliotecas seleccionadas", status=200
        )


@login_required
@user_passes_test(is_staff)
def group_library_item_viewer(request, group_id, pk):
    """
    Visor fullscreen para items de biblioteca de grupo.
    TINY VIEW: Similar a my_library viewer.
    Soporta visualización de elementos específicos dentro de ScorePages.
    """
    group = get_object_or_404(Group, pk=group_id)

    # Verificar que el profesor pertenece a este grupo
    if not group.teachers.filter(pk=request.user.pk).exists():
        messages.error(request, "No tienes permiso para ver este contenido.")
        return redirect("clases:group_library_index", group_id=group_id)

    item = get_object_or_404(GroupLibraryItem, pk=pk, group=group)

    score_media = item.get_related_scorepage_media()

    # Preparar documentos según tipo de contenido
    documents = {
        "pdfs": [],
        "images": [],
        "audios": [],
    }

    content_type = item.content_type.model
    content = item.content_object

    # Verificar si se solicita un elemento específico dentro de una ScorePage
    element_type = request.GET.get("element_type")
    element_id = request.GET.get("element_id")

    # Clasificar según tipo
    if content_type == "document":
        # Wagtail Document
        if hasattr(content, "file"):
            filename = content.file.name.lower()
            if filename.endswith(".pdf"):
                documents["pdfs"].append(content)
            elif filename.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")):
                documents["audios"].append(content)
    elif content_type == "image":
        # Wagtail Image
        documents["images"].append(content)
    elif content_type == "scorepage":
        # ScorePage: extraer sus PDFs, audios, imágenes
        if hasattr(content, "content"):
            for block in content.content:
                if block.block_type == "pdf_score":
                    pdf_file = block.value.get("pdf_file")
                    if pdf_file:
                        # Si se solicita un elemento específico, solo añadir ese
                        if (
                            element_type == "pdf"
                            and element_id
                            and str(pdf_file.pk) == element_id
                        ):
                            documents["pdfs"] = [pdf_file]
                            break
                        elif not element_type:
                            documents["pdfs"].append(pdf_file)
                elif block.block_type == "audio":
                    audio_file = block.value.get("audio_file")
                    if audio_file:
                        if (
                            element_type == "audio"
                            and element_id
                            and str(audio_file.pk) == element_id
                        ):
                            documents["audios"] = [audio_file]
                            break
                        elif not element_type:
                            documents["audios"].append(audio_file)
                elif block.block_type == "image":
                    image = block.value.get("image")
                    if image:
                        if (
                            element_type == "image"
                            and element_id
                            and str(image.pk) == element_id
                        ):
                            documents["images"] = [image]
                            break
                        elif not element_type:
                            documents["images"].append(image)

    return render(
        request,
        "clases/group_library/viewer.html",
        {
            "group": group,
            "item": item,
            "documents": documents,
            "score_media": score_media,
        },
    )


@login_required
def class_session_item_viewer(request, session_id, item_id):
    """
    Visor fullscreen para items de sesión.
    - Para profesores: pueden ver items de sus sesiones
    - Para estudiantes: pueden ver items de sesiones de su grupo
    TINY VIEW: Usa mismo template que my_library para consistencia.
    Soporta parámetro 'from' para volver a la vista correcta (view o edit).
    """
    user = request.user
    is_teacher = user.is_staff and hasattr(user, "teaching_groups")

    session = get_object_or_404(ClassSession, pk=session_id)

    # Verificar permisos según rol
    if is_teacher:
        # Profesor: debe ser el creador de la sesión
        if session.teacher != user:
            messages.error(request, "No tienes permiso para ver este contenido.")
            return redirect("clases:class_session_list")
    else:
        # Estudiante: debe estar matriculado en el grupo de la sesión
        is_enrolled = Enrollment.objects.filter(
            user=user, group=session.group, is_active=True
        ).exists()

        if not is_enrolled:
            messages.error(request, "No tienes permiso para ver este contenido.")
            return redirect("clases:class_session_list")

    item = get_object_or_404(ClassSessionItem, pk=item_id, session=session)

    score_media = item.get_related_scorepage_media()

    # Preparar documentos según tipo de contenido
    documents = {
        "pdfs": [],
        "images": [],
        "audios": [],
    }

    content_type = item.content_type.model
    content = item.content_object

    # Clasificar según tipo (similar a my_library)
    if content_type == "document":
        # Wagtail Document
        if hasattr(content, "file"):
            filename = content.file.name.lower()
            if filename.endswith(".pdf"):
                documents["pdfs"].append(content)
            elif filename.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")):
                documents["audios"].append(content)
    elif content_type == "image":
        # Wagtail Image
        documents["images"].append(content)
    elif content_type == "blogpage":
        # BlogPage: usar viewer específico para blogs
        return render(
            request,
            "clases/viewers/blog_viewer.html",
            {
                "blog_page": content,
                "session": session,
                "item": item,
            },
        )

    # Determinar URL de retorno según parámetro 'from' y rol
    from_view = request.GET.get("from", "edit")
    if from_view == "view" or not is_teacher:
        # Estudiantes siempre vuelven a 'view'
        back_url = reverse("clases:class_session_view", args=[session_id])
    else:
        # Profesores pueden volver a 'edit'
        back_url = reverse("clases:class_session_edit", args=[session_id])

    # Usar el mismo template de my_library para consistencia
    return render(
        request,
        "my_library/viewer.html",
        {
            "item": item,
            "documents": documents,
            "back_url": back_url,
            "score_media": score_media,
        },
    )


# =============================================================================
# ASIGNACIÓN MASIVA A BIBLIOTECAS PERSONALES DE ESTUDIANTES
# =============================================================================


@login_required
@user_passes_test(is_staff)
def show_assign_to_students_modal(request, group_id):
    """
    Vista HTMX que devuelve el modal con selector múltiple de estudiantes.
    TINY VIEW: solo renderiza el modal con los estudiantes del grupo.
    """
    group = get_object_or_404(Group, pk=group_id)

    # Verificar que el profesor pertenece a este grupo
    if not group.teachers.filter(pk=request.user.pk).exists():
        return HttpResponse("No autorizado", status=403)

    content_type_id = request.GET.get("content_type_id")
    object_id = request.GET.get("object_id")

    content_type = get_object_or_404(ContentType, id=content_type_id)
    content_object = content_type.get_object_for_this_type(pk=object_id)

    # Obtener estudiantes del grupo ordenados por nombre
    students = (
        Student.objects.filter(group=group)
        .select_related("user")
        .order_by("user__name")
    )

    return render(
        request,
        "clases/group_library/partials/assign_to_students_modal.html",
        {
            "group": group,
            "content_object": content_object,
            "content_type": content_type,
            "students": students,
        },
    )


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def assign_to_students(request, group_id):
    """
    Asigna un recurso a las bibliotecas personales de múltiples estudiantes.
    TINY VIEW: orquesta y delega al modelo (FAT MODEL).
    """
    from my_library.models import LibraryItem

    group = get_object_or_404(Group, pk=group_id)

    # Verificar que el profesor pertenece a este grupo
    if not group.teachers.filter(pk=request.user.pk).exists():
        return HttpResponse("No autorizado", status=403)

    content_type_id = request.POST.get("content_type_id")
    object_id = request.POST.get("object_id")
    student_ids = request.POST.getlist("student_ids")

    # Validar parámetros
    if not content_type_id or not object_id:
        return HttpResponse("Error: Parámetros inválidos", status=400)

    if not student_ids:
        return HttpResponse(
            '<div class="alert alert-warning"><span>⚠️ Debes seleccionar al menos un estudiante</span></div>',
            status=200,
        )

    content_type = get_object_or_404(ContentType, pk=content_type_id)
    model_class = content_type.model_class()
    content_object = get_object_or_404(model_class, pk=object_id)

    # Procesar cada estudiante
    added_count = 0
    already_exists_count = 0
    students_with_item = []

    for student_id in student_ids:
        student = get_object_or_404(Student, pk=student_id, group=group)

        if student.user:
            # Usar el método del modelo (FAT MODEL)
            item, created = LibraryItem.add_to_library(
                user=student.user, content_object=content_object
            )

            if created:
                added_count += 1
            else:
                already_exists_count += 1
                students_with_item.append(student.user.name)

    # Renderizar respuesta con resumen
    response_html = f'<div class="alert alert-success">'
    response_html += (
        f"<span>✓ Añadido a {added_count} biblioteca(s) personal(es)</span>"
    )
    if already_exists_count > 0:
        response_html += (
            f'<br><small class="opacity-70">Ya estaba en la biblioteca de {already_exists_count} estudiante(s): '
            f'{", ".join(students_with_item[:3])}'
        )
        if len(students_with_item) > 3:
            response_html += f" y {len(students_with_item) - 3} más"
        response_html += "</small>"
    response_html += "</div>"

    return HttpResponse(response_html, status=200)
