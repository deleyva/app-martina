from django import template
from django.contrib.contenttypes.models import ContentType
from my_library.models import LibraryItem

register = template.Library()


@register.simple_tag(takes_context=True)
def is_in_library(context, content_object):
    """Verifica si un objeto está en la biblioteca del usuario"""
    user = context.request.user
    if not user.is_authenticated:
        return False
    return LibraryItem.is_in_library(user, content_object)


@register.inclusion_tag("my_library/partials/add_button.html", takes_context=True)
def library_button(context, content_object):
    """Renderiza botón de añadir/quitar de biblioteca con HTMX

    Para profesores: muestra un botón que abre modal con opciones múltiples
    Para estudiantes: toggle simple entre añadir/quitar

    RESTRICCIÓN: No se muestran botones para ScorePages completas en bibliotecas personales.
    Solo se pueden añadir elementos individuales (PDFs, audios, imágenes).
    """
    from clases.models import Student, GroupLibraryItem

    if content_object is None:
        return {
            "content_object": None,
            "content_type": None,
            "in_library": False,
            "user": context.request.user if hasattr(context, "request") else None,
            "is_teacher": False,
            "teaching_groups": [],
            "all_students": [],
            "is_scorepage": False,
            "groups_with_content": set(),
        }

    user = context.request.user
    in_library = False
    teaching_groups = []
    all_students = []
    is_teacher = False
    groups_with_content = set()  # IDs de grupos que ya tienen este contenido

    content_type = ContentType.objects.get_for_model(content_object)

    # RESTRICCIÓN: No mostrar botón para ScorePages (solo elementos individuales)
    is_scorepage = content_type.model == "scorepage"

    if user.is_authenticated:
        in_library = LibraryItem.is_in_library(user, content_object)

        # Verificar si es profesor y obtener sus grupos
        if user.is_staff and hasattr(user, "teaching_groups"):
            teaching_groups = list(user.teaching_groups.all())
            is_teacher = len(teaching_groups) > 0

            # Obtener todos los estudiantes de los grupos del profesor
            if is_teacher:
                all_students = (
                    Student.objects.filter(group__in=teaching_groups)
                    .select_related("user", "group")
                    .order_by("group__name", "user__name")
                )

                # Verificar qué grupos ya tienen este contenido
                existing_items = GroupLibraryItem.objects.filter(
                    group__in=teaching_groups,
                    content_type=content_type,
                    object_id=content_object.pk,
                ).values_list("group_id", flat=True)
                groups_with_content = set(existing_items)

    return {
        "content_object": content_object,
        "content_type": content_type,
        "in_library": in_library,
        "user": user,
        "is_teacher": is_teacher,
        "teaching_groups": teaching_groups,
        "all_students": all_students,
        "is_scorepage": is_scorepage,
        "groups_with_content": groups_with_content,
    }
