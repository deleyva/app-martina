from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from pathlib import Path
import secrets
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import redirect_to_login
from django.views.decorators.http import require_http_methods
from django.contrib.contenttypes.models import ContentType
import json

from martina_bescos_app.users.permisos import es_profesor, grupo_del_profesor
from my_library import medios

# Los tres formatos que puede soltar `MediaRecorder` según el navegador. Las dos
# tablas son la misma correspondencia leída en cada sentido: una para nombrar el
# fichero al subirlo y otra para devolverlo con su tipo al servirlo.
EXTENSION_DE_AUDIO = {
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/m4a": ".m4a",
    "audio/ogg": ".ogg",
}
TIPO_DE_AUDIO = {
    ".webm": "audio/webm",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
}


LIMITE_DE_AUDIO = 20 * 1024 * 1024  # 20 MB


def _preparar_audio(audio_file, prefijo):
    """Valida y renombra una nota de voz subida. Devuelve un 400 si no vale.

    La usan el cierre de la clase y las notas tomadas durante ella: el límite y
    el nombre tienen que ser los mismos en las dos, o la primera vez que se
    toque uno se olvidará el otro.

    **El nombre es impredecible a propósito**, no `reflexion_sesion_<pk>`: el id
    de la sesión lo tiene el alumnado en su propia barra de direcciones, así que
    ese nombre se adivinaba entero. El portero de verdad es la vista que sirve
    el fichero; esto es el cinturón por si algún día falla el tirante.
    """
    if not audio_file:
        return None
    if audio_file.size > LIMITE_DE_AUDIO:
        return HttpResponse("Audio demasiado grande (máx. 20 MB)", status=400)
    ext = EXTENSION_DE_AUDIO.get(audio_file.content_type, ".webm")
    audio_file.name = f"{prefijo}_{secrets.token_urlsafe(12)}{ext}"
    return None


def _servir_audio(fichero):
    extension = Path(fichero.name).suffix.lower()
    tipo = TIPO_DE_AUDIO.get(extension, "application/octet-stream")
    return FileResponse(fichero.open("rb"), content_type=tipo)

from .models import (
    Group,
    ClassSession,
    ClassSessionItem,
    Student,
    GroupInvitation,
    Enrollment,
)


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
    elif status == "habilitado":
        messages.success(
            request,
            "Ya puedes usar la aplicación como profesor. "
            "Empieza creando un grupo y asignándole libros.",
        )
    elif status == "ya_era_profesor":
        messages.info(request, "Ya tenías acceso como profesor.")
    else:
        messages.error(
            request,
            "No se ha podido procesar la invitación. Contacta con tu profesor.",
        )

    return redirect("clases:class_session_list")


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
    is_teacher = es_profesor(user)

    # `?archivadas=1` enseña justamente lo contrario: lo que está fuera del día a
    # día. No es un "ver todo": si mezclara, la vista archivada no serviría para
    # revisar un curso cerrado sin el ruido del actual.
    viendo_archivadas = request.GET.get("archivadas") == "1"

    if is_teacher:
        grupos_dia_a_dia = Group.del_profesor(user)
        grupos_archivados = Group.del_profesor(user, incluir_archivados=True).filter(
            archivado=True
        )
        groups = grupos_archivados if viendo_archivadas else grupos_dia_a_dia
        sessions = (
            ClassSession.objects.filter(teacher=user, group__in=groups)
            .select_related("group")
        )
    else:
        grupos_dia_a_dia = Group.matriculados_de(user)
        grupos_archivados = Group.matriculados_de(user, incluir_archivados=True).filter(
            archivado=True
        )
        groups = grupos_archivados if viendo_archivadas else grupos_dia_a_dia
        sessions = ClassSession.objects.filter(
            group__in=groups
        ).select_related("group", "teacher")

    return render(
        request,
        "clases/class_sessions/list.html",
        {
            "sessions": sessions,
            "groups": groups,
            "viendo_archivadas": viendo_archivadas,
            "n_archivados": grupos_archivados.count(),
            "is_teacher": is_teacher,
        },
    )


@login_required
@user_passes_test(es_profesor)
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

        group = grupo_del_profesor(request.user, group_id)

        # Verificar que el profesor pertenece a este grupo
        if not group.teachers.filter(pk=request.user.pk).exists():
            messages.error(
                request, "No tienes permiso para crear sesiones en este grupo."
            )
            return redirect("clases:class_session_list")

        # Y que el grupo siga vivo. Esconderlo del selector no basta: un
        # formulario guardado o un POST a mano crearía una clase en un curso ya
        # cerrado, y nadie la vería nunca porque su grupo está archivado.
        if group.archivado:
            messages.error(
                request,
                f"«{group.name}» está archivado. Desarchívalo si quieres darle clase otra vez.",
            )
            return redirect("clases:class_session_list")

        # Crear sesión
        session = ClassSession.objects.create(
            teacher=request.user, group=group, date=date, title=title, notes=notes
        )

        messages.success(request, f"Sesión '{title}' creada exitosamente.")
        return redirect("clases:class_session_edit", pk=session.pk)

    # GET: Mostrar formulario
    groups = Group.del_profesor(request.user)
    return render(
        request,
        "clases/class_sessions/create.html",
        {"groups": groups},
    )


@login_required
@user_passes_test(es_profesor)
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

        group = grupo_del_profesor(request.user, group_id)

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
@user_passes_test(es_profesor)
@require_http_methods(["POST"])
def class_session_close(request, pk):
    """
    Cerrar sesión de clase guardando la reflexión del profesor (texto y/o audio).
    TINY VIEW: delega en ClassSession.close() (FAT MODEL).
    Acepta multipart/form-data: reflection (texto), reflection_audio (blob webm/opus).
    """
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)

    reflection_text = request.POST.get("reflection", "").strip()
    audio_file = request.FILES.get("reflection_audio")

    error = _preparar_audio(audio_file, f"reflexion_{session.pk}")
    if error:
        return error

    session.close(reflection_text=reflection_text, audio_file=audio_file)

    # Actualizar cobertura del plan de programación (si existe la app)
    try:
        from programacion.services import update_coverage_for_session

        update_coverage_for_session(session)
    except ImportError:
        pass

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return HttpResponse("ok")

    messages.success(request, "Clase finalizada. Reflexión guardada.")
    return redirect("clases:class_session_view", pk=session.pk)


@login_required
@user_passes_test(es_profesor)
def class_session_reflection_audio(request, pk):
    """La nota de voz de una reflexión, solo para el profesor que la grabó.

    **Por qué no se sirve por `/media/`.** nginx entrega ese directorio tal
    cual, sin pasar por Django: cualquiera con la URL se baja el fichero. Y la
    URL se adivinaba entera, porque el nombre se construía con el id de la
    sesión, que el alumnado tiene delante en su propia barra de direcciones.
    Una reflexión de clase puede hablar de un alumno con nombre y apellidos.

    Es la misma forma que usa `musica.servido` con los PDF restringidos: el
    fichero sale por una vista que pregunta quién lo pide, y nginx tiene cerrado
    el atajo (`location ^~ /media/class_reflections/`).
    """
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)

    if not session.reflection_audio:
        raise Http404("Esta sesión no tiene nota de voz.")

    return _servir_audio(session.reflection_audio)


# ── Notas de voz durante la clase ───────────────────────────────────────────
#
# En clase solo se graba: un toque en el micrófono del visor. Whisper transcribe
# en segundo plano (`clases.tasks.transcribir_nota`), y al final el profesor
# revisa cada nota bajo «💭 Reflexión de la clase»: corrige la transcripción y
# la acepta —pasa a la reflexión y el audio se borra— o la descarta. Nada de
# esto cierra la clase: ni `close()` ni la cobertura de la programación.


def _nota_a_json(session, nota):
    return {
        "pk": nota.pk,
        "cabecera": nota.cabecera(),
        "estado": nota.estado,
        "transcripcion": nota.transcripcion,
        "audio_url": reverse("clases:class_session_note_audio", args=[session.pk, nota.pk]),
        "aceptar_url": reverse("clases:class_session_note_aceptar", args=[session.pk, nota.pk]),
        "descartar_url": reverse(
            "clases:class_session_note_descartar", args=[session.pk, nota.pk]
        ),
    }


@login_required
@user_passes_test(es_profesor)
@require_http_methods(["POST"])
def class_session_notes(request, pk):
    """Guarda una nota de voz grabada en el visor. Solo audio."""
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)

    audio_file = request.FILES.get("audio")
    if not audio_file:
        return JsonResponse({"error": "Falta el audio."}, status=400)
    error = _preparar_audio(audio_file, f"nota_{session.pk}")
    if error:
        return error

    # Solo un elemento de ESTA sesión: el id viene del cliente.
    item = None
    item_pk = request.POST.get("item")
    if item_pk and item_pk.isdigit():
        item = session.items.filter(pk=int(item_pk)).first()

    nota = session.anadir_nota(audio_file=audio_file, item=item)
    return JsonResponse({"ok": True, "nota": _nota_a_json(session, nota)})


@login_required
@user_passes_test(es_profesor)
def class_session_notes_lista(request, pk):
    """Las notas de voz que esperan revisión, para las dos pantallas."""
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    return JsonResponse(
        {"notas": [_nota_a_json(session, n) for n in session.notas.all()]}
    )


@login_required
@user_passes_test(es_profesor)
@require_http_methods(["POST"])
def class_session_note_aceptar(request, pk, nota_pk):
    """Pasa el texto corregido a la reflexión y borra la nota con su audio."""
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    nota = get_object_or_404(session.notas, pk=nota_pk)
    try:
        linea = nota.aceptar(request.POST.get("texto", ""))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"ok": True, "linea": linea})


@login_required
@user_passes_test(es_profesor)
@require_http_methods(["POST"])
def class_session_note_descartar(request, pk, nota_pk):
    """Borra la nota y su audio sin tocar la reflexión."""
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    nota = get_object_or_404(session.notas, pk=nota_pk)
    nota.descartar()
    return JsonResponse({"ok": True})


@login_required
@user_passes_test(es_profesor)
def class_session_reflection_actual(request, pk):
    """La reflexión tal como está AHORA en la base.

    La pantalla de cierre del visor la pide al abrirse. Sin esto rellenaba su
    cuadro con la reflexión de cuando se cargó la página —vacía, al empezar la
    clase—, y como `close()` sobrescribe, finalizar habría borrado todas las
    notas de la hora.
    """
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    return JsonResponse({"reflection": session.reflection})


@login_required
@user_passes_test(es_profesor)
def class_session_note_audio(request, pk, nota_pk):
    """El audio de una nota de clase, solo para el profesor de la sesión.

    Mismo portero que `class_session_reflection_audio`: nginx cierra
    `/media/class_reflections/` y el fichero solo sale por aquí.
    """
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    nota = get_object_or_404(session.notas, pk=nota_pk)
    if not nota.audio:
        raise Http404("Esta nota no tiene audio.")
    return _servir_audio(nota.audio)


@login_required
@user_passes_test(es_profesor)
@require_http_methods(["POST"])
def class_session_reopen(request, pk):
    """Reabrir una sesión cerrada."""
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    session.reopen()
    messages.info(request, "Sesión reabierta.")
    return redirect("clases:class_session_view", pk=session.pk)


@login_required
def class_session_view(request, pk):
    """
    Ver sesión de clase (solo lectura).
    - Para profesores: pueden ver sus propias sesiones
    - Para estudiantes: pueden ver sesiones de sus grupos (multi-grupo)
    TINY VIEW: solo renderiza.
    """
    user = request.user
    is_teacher = es_profesor(user)

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
def class_session_present(request, pk):
    """
    Modo presentación fullscreen para sesión de clase.
    Igual que study_session_view de my_library pero sin proficiency.
    Usa fetch item-by-item con los mismos viewers (PDF, imagen, audio, embed).
    """
    user = request.user
    is_teacher = es_profesor(user)

    if is_teacher:
        session = get_object_or_404(ClassSession, pk=pk, teacher=user)
    else:
        session = get_object_or_404(ClassSession, pk=pk)
        is_enrolled = Enrollment.objects.filter(
            user=user, group=session.group, is_active=True
        ).exists()
        if not is_enrolled:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("No tienes permiso para ver esta sesión.")

    items = session.get_items_ordered()

    # Qué elementos de la clase están marcados para irse a casa. En una consulta
    # para toda la sesión: preguntarlo por elemento daría una consulta por fila.
    from clases.models import GroupBookItem

    marcados = set(
        GroupBookItem.objects.filter(
            group_book__in=[i.group_book_id for i in items if i.group_book_id],
            a_casa=True,
        ).values_list("group_book_id", "content_type_id", "object_id")
    )
    con_casita = {
        item.pk
        for item in items
        if (item.group_book_id, item.content_type_id, item.object_id) in marcados
    }

    # alphaTab pesa 1,1 MB y hay que precargarlo en el `<head>`: los visores
    # llegan por fetch y su script inline corre antes de que una librería
    # pedida en ese momento haya terminado de bajar. Precargarlo en toda clase
    # sería pagarlo también en las que no llevan ninguna tablatura, así que se
    # mira aquí, en el bucle que ya recorre la sesión entera.
    tiene_gp = False
    # Lo mismo con la letra con acordes, por la misma razón, aunque pesa menos.
    tiene_chordpro = False

    playlist = []
    for item in items:
        if not item.content_object:
            continue
        clave = medios.clave_de(item.content_object, item.content_type.model)
        if clave == "gp_files":
            tiene_gp = True
        elif clave == "chordpro":
            tiene_chordpro = True
        # `page_url` alimenta el botón de "ver la página entera": el elemento que
        # se estudia es un medio suelto —una imagen, un PDF—, y a veces hace
        # falta el texto que lo rodea. Se calcula aquí y no en el cliente porque
        # la URL sale del árbol de Wagtail.
        pagina = item.source_page
        playlist.append(
            {
                "pk": item.pk,
                "title": item.get_content_title(),
                "icon": item.get_icon(),
                "type": item.get_content_type_name(),
                "seccion": item.get_seccion_display() if item.seccion else "",
                "visto": item.visto,
                "tratado": item.tratado,
                "tiene_libro": item.group_book_id is not None,
                "a_casa": item.pk in con_casita,
                "page_url": pagina.get_url() if pagina else "",
                "page_title": pagina.title if pagina else "",
                # Pase de preguntas (fase 76): su pantalla se pinta sola, pero
                # la presentación necesita saberlo para no tratarlo como medio.
                "pase": item.object_id if item.content_type.model == "pase" else None,
                # Evaluable (fase 62). Solo para el profesor: el alumnado ve la
                # misma presentación y no tiene botón de evaluar.
                "instrumento": (
                    {"id": item.instrumento_id, "nombre": item.instrumento.nombre}
                    if is_teacher and item.instrumento_id
                    else None
                ),
            }
        )

    return render(
        request,
        "clases/class_sessions/present.html",
        {
            "session": session,
            # `<`, `>` y `&` escapados: el JSON va dentro de un <script> con
            # `|safe`, y un título o un nombre de instrumento con `</script>`
            # cerraba el bloque (revisión independiente, 2026-10-04).
            "playlist_json": json.dumps(playlist)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026"),
            "is_teacher": is_teacher and session.teacher == user,
            "tiene_gp": tiene_gp,
            "tiene_chordpro": tiene_chordpro,
            # Fase 70: si aún no se ha pasado lista, el plano sale lo primero.
            "lista_pasada": _lista_pasada(session) if is_teacher and session.teacher == user else True,
        },
    )


def _lista_pasada(session):
    from clases.models import PaseDeLista

    return PaseDeLista.objects.filter(session=session, pasada_at__isnull=False).exists()


@login_required
def class_session_item_content(request, session_id, item_id):
    """
    Devuelve HTML del viewer para un item de sesión (sin wrapper).
    Análogo a my_library:study_item_content pero para ClassSessionItem.
    """
    user = request.user
    is_teacher = es_profesor(user)

    session = get_object_or_404(ClassSession, pk=session_id)
    if is_teacher:
        if session.teacher != user:
            return HttpResponse("No autorizado", status=403)
    else:
        is_enrolled = Enrollment.objects.filter(
            user=user, group=session.group, is_active=True
        ).exists()
        if not is_enrolled:
            return HttpResponse("No autorizado", status=403)

    item = get_object_or_404(ClassSessionItem, pk=item_id, session=session)
    return render_item_content(request, item)


def render_item_content(request, item):
    """Pinta el contenido de un elemento con el visor de `my_library`.

    Separado de la vista para que la previsualización de «preparar» enseñe el
    elemento por EL MISMO camino que lo enseñará la clase. `item` puede ser un
    `ClassSessionItem` sin guardar: aquí solo se le piden `content_type` y
    `content_object`, y las plantillas de Django resuelven a vacío lo que no
    exista.
    """
    content_type = item.content_type.model
    content = item.content_object

    # El pase de preguntas (fase 76) no es un medio: tiene su propia pantalla.
    if content_type == "pase":
        from preguntas.views_pase import render_pase_en_clase

        return render_pase_en_clase(request, item)

    # BlogPages/DictadoPages: show in iframe via a simple redirect partial
    if content_type in ("recursopage", "dictadopage", "scorepage"):
        if hasattr(content, "get_url"):
            page_url = content.get_url()
            html = (
                f'<div style="width:100%;height:100%;">'
                f'<iframe src="{page_url}" style="width:100%;height:100%;border:none;" '
                f'allowfullscreen></iframe></div>'
            )
            return HttpResponse(html)

    score_media = item.get_related_scorepage_media()

    # El cajón de cada tipo de medio lo decide `my_library.medios`, y solo él.
    # Cuando esta clasificación vivía aquí escrita a mano no conocía los
    # ficheros de Guitar Pro, así que una tablatura acababa en el «No se
    # encontró contenido para visualizar» en mitad de una clase.
    documents = medios.clasificar(content, content_type)

    if score_media and score_media.get("embeds"):
        for embed_val in score_media["embeds"]:
            documents["embeds"].append(embed_val)

    # Reutilizar el mismo partial que my_library study mode
    return render(
        request,
        "my_library/partials/study_item_content.html",
        {
            "item": item,
            "documents": documents,
            "score_media": score_media,
            # El tono de clase de las canciones con acordes es el de ESTE
            # grupo (fase 63).
            "grupo_tono": getattr(getattr(item, "session", None), "group", None),
        },
    )


@login_required
@user_passes_test(es_profesor)
def class_session_edit(request, pk):
    """
    Editar sesión de clase con drag & drop.
    TINY VIEW: solo renderiza. Los elementos llegan desde los libros del grupo.
    """
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    items = session.get_items_ordered()

    return render(
        request,
        "clases/class_sessions/edit.html",
        {"session": session, "items": items},
    )


@login_required
@user_passes_test(es_profesor)
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
        source_page_id = request.POST.get("source_page_id")

        content_type = get_object_or_404(ContentType, id=content_type_id)
        content_object = content_type.get_object_for_this_type(pk=object_id)

        try:
            # Lógica en el modelo (FAT MODEL)
            item = ClassSessionItem.add_to_session(
                session=session,
                content_object=content_object,
                notes=notes,
                source_page_id=source_page_id,
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
@user_passes_test(es_profesor)
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
@user_passes_test(es_profesor)
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
@user_passes_test(es_profesor)
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
            # Sin la página de origen la copia pinta la tablatura sin el botón
            # de Songsterr y sin el de «ver la página entera»: los dos salen de
            # ella, no del documento.
            source_page_id=item.source_page_id,
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
@user_passes_test(es_profesor)
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
# VISTAS DE BIBLIOTECA MÚLTIPLE (Personal + Estudiantes)
# ============================================================================


@require_http_methods(["POST"])
@login_required
@user_passes_test(es_profesor, login_url="/accounts/login/", redirect_field_name=None)
def add_to_multiple_libraries(request):
    """
    Añade un recurso a múltiples bibliotecas (la personal y/o las de estudiantes).
    TINY VIEW: orquesta y delega al modelo.
    """
    from my_library.models import LibraryItem

    content_type_id = request.POST.get("content_type_id")
    object_id = request.POST.get("object_id")
    personal_library = request.POST.get("personal_library") == "true"
    student_ids = request.POST.getlist("student_ids")

    # Validar parámetros
    if not content_type_id or not object_id:
        return HttpResponse("Error: Parámetros inválidos", status=400)

    content_type = get_object_or_404(ContentType, pk=content_type_id)
    model_class = content_type.model_class()
    content_object = get_object_or_404(model_class, pk=object_id)

    added_count = 0
    already_exists_count = 0

    source_page_id = request.POST.get("source_page_id")

    # Añadir a biblioteca personal del profesor
    if personal_library:
        item, created = LibraryItem.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=object_id,
        )
        if created:
            added_count += 1
        if source_page_id and not item.source_page_id:
            item.source_page_id = source_page_id
            item.save(update_fields=["source_page_id"])
        if not created:
            already_exists_count += 1

    # Añadir a bibliotecas personales de estudiantes
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    for student_id in student_ids:
        # Asumimos que student_id es el ID del usuario (User)
        # ya que el modelo Student está obsoleto
        student_user = get_object_or_404(User, pk=student_id)

        # Verificar que el profesor tiene algún grupo en común con el estudiante
        # a través de una matrícula activa
        has_common_group = Group.objects.filter(
            teachers=request.user,
            enrollments__user=student_user,
            enrollments__is_active=True
        ).exists()

        if not has_common_group:
            continue
            
        # Añadir a la biblioteca del usuario usando el método del modelo (FAT MODEL)
        try:
            item, created = LibraryItem.add_to_library(
                user=student_user,
                content_object=content_object
            )
            if created:
                added_count += 1
            else:
                already_exists_count += 1
        except ValueError:
            # Si no se puede añadir (ej: es una ScorePage completa), ignoramos silenciosamente
            # o podríamos agregar un contador de errores
            continue

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
def class_session_item_viewer(request, session_id, item_id):
    """
    Visor fullscreen para items de sesión.
    - Para profesores: pueden ver items de sus sesiones
    - Para estudiantes: pueden ver items de sesiones de su grupo
    TINY VIEW: Usa mismo template que my_library para consistencia.
    Soporta parámetro 'from' para volver a la vista correcta (view o edit).
    """
    user = request.user
    is_teacher = es_profesor(user)

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

    content_type = item.content_type.model
    content = item.content_object

    # Verificar si se solicita un elemento específico
    element_type = request.GET.get("element_type")
    element_id = request.GET.get("element_id")
    embed_url = request.GET.get("embed_url")
    # Antes se leía más abajo, después de usarse en la redirección de las
    # páginas: toda canción o dictado abierto desde una sesión daba un 500
    # (`UnboundLocalError`). Cubierto por `ClassSessionItemViewerPaginaTest`.
    from_view = request.GET.get("from", "edit")

    # BlogPages y DictadoPages: redirigir a su visualización normal de Wagtail
    # EXCEPTO si estamos intentando ver un embed específico de la misma
    if content_type in ["recursopage", "dictadopage"] and element_type != "embed":
        if hasattr(content, "get_url"):
            url = content.get_url()
            # Pasar contexto de sesión para que el botón "Volver" regrese aquí
            if from_view == "view":
                url += f"?from_session={session_id}"
            elif from_view == "edit":
                url += f"?from_session={session_id}&from=edit"
            return redirect(url)

    score_media = item.get_related_scorepage_media()

    # Un solo clasificador, en `my_library.medios`. El `enlaceexterno` es
    # material con licencia que vive fuera (Blink Learning) y no se incrusta: su
    # cookie de sesión no viaja en un iframe de otro sitio, así que el visor
    # ofrece un botón que lo abre en una ventana con nombre fijo.
    documents = medios.clasificar(content, content_type)

    # Los embeds de una ScorePage se añaden aparte: no son el medio del elemento
    # sino lo que cuelga de su página de origen.
    if score_media and score_media.get("embeds"):
        for embed_val in score_media["embeds"]:
            if element_type == "embed" and embed_url == embed_val.url:
                documents["embeds"] = [embed_val]
                break
            elif not element_type:
                documents["embeds"].append(embed_val)

    # Determinar URL de retorno según parámetro 'from' y rol
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
