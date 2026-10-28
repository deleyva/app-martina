from django import template

from musica.letras import puede_editar

register = template.Library()


@register.filter
def editable_por(page, user):
    """`{% if page|editable_por:request.user %}`: el permiso de Wagtail."""
    return bool(page) and puede_editar(page, user)


@register.simple_tag
def pistas_de_practica(page, user):
    """Lo que necesita el reproductor de práctica del visor (fase 82).

    `mostrar` es falso cuando no hay nada que oír ni permiso para subir: el
    alumno de una canción sin pistas no ve ningún botón nuevo.
    """
    from django.urls import reverse

    puede = bool(page) and puede_editar(page, user)
    pistas = [p.a_json() for p in page.pistas_de_practica.all()] if page else []
    return {
        "mostrar": bool(pistas) or puede,
        "datos": {
            "pistas": pistas,
            "puedeEditar": puede,
            "subir": reverse("musica:pista_subir", args=[page.pk]) if puede else "",
        },
    }
