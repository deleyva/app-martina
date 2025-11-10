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


@register.inclusion_tag(
    "my_library/partials/add_button.html", takes_context=True
)
def library_button(context, content_object):
    """Renderiza botón de añadir/quitar de biblioteca con HTMX"""
    user = context.request.user
    in_library = False

    if user.is_authenticated:
        in_library = LibraryItem.is_in_library(user, content_object)

    content_type = ContentType.objects.get_for_model(content_object)

    return {
        "content_object": content_object,
        "content_type": content_type,
        "in_library": in_library,
        "user": user,
    }
