from django import template

from musica.letras import puede_editar

register = template.Library()


@register.filter
def editable_por(page, user):
    """`{% if page|editable_por:request.user %}`: el permiso de Wagtail."""
    return bool(page) and puede_editar(page, user)
