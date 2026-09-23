from django import template

register = template.Library()

CLASES_CUALITATIVA = {
    "IN": "badge-error",
    "SU": "badge-warning",
    "BI": "badge-info",
    "NT": "badge-primary",
    "SB": "badge-success",
}


@register.filter
def dict_get(diccionario, clave):
    """`{{ dic|dict_get:clave }}`: lo que Django no trae de serie."""
    if not diccionario:
        return None
    return diccionario.get(clave)


@register.filter
def clase_cualitativa(calificacion):
    return CLASES_CUALITATIVA.get(calificacion or "", "badge-ghost")
