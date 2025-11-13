from django import template
from django.contrib.contenttypes.models import ContentType
from evaluations.models import Group, GroupLibraryItem

register = template.Library()


@register.simple_tag(takes_context=True)
def group_library_button(context, group, content_object):
    """
    Genera botón "Añadir/Quitar de Biblioteca del Grupo" con HTMX.
    Detecta si ya está en la biblioteca del grupo.
    Usa clases de DaisyUI.
    
    Uso:
        {% load group_library_tags %}
        {% group_library_button group score_page %}
    """
    request = context.get("request")
    
    # Solo mostrar para staff
    if not request or not request.user.is_staff:
        return ""
    
    # Verificar que el profesor pertenece al grupo
    if not isinstance(group, Group) or not group.teachers.filter(pk=request.user.pk).exists():
        return ""
    
    content_type = ContentType.objects.get_for_model(content_object)
    in_library = GroupLibraryItem.is_in_library(group, content_object)
    
    # Renderizar el partial
    from django.template.loader import render_to_string
    return render_to_string(
        "evaluations/group_library/partials/add_button.html",
        {
            "group": group,
            "content_object": content_object,
            "content_type": content_type,
            "in_library": in_library,
            "user": request.user,
        },
        request=request,
    )
