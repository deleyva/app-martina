from django import template

from preguntas.models import Pregunta

register = template.Library()


@register.filter
def letra(indice):
    """0 → A, 1 → B… la letra de la tarjeta es el índice de la opción."""
    try:
        return Pregunta.LETRAS[int(indice)]
    except (ValueError, TypeError, IndexError):
        return "?"


@register.filter
def get_item(diccionario, clave):
    try:
        return diccionario.get(clave)
    except AttributeError:
        return None
