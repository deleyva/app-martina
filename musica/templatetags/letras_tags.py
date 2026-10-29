import re

from django import template

from musica.letras import puede_editar

register = template.Library()

# El identificador de once caracteres de un vídeo, venga como venga el enlace:
# `watch?v=`, `youtu.be/`, `embed/` o `shorts/`.
_YOUTUBE_ID = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:[^\"'\s<>]*?&(?:amp;)?)?v=|embed/|shorts/)|youtu\.be/)([\w-]{11})"
)


def videoclip_de(page):
    """El videoclip de la canción: el primer vídeo de YouTube del cuerpo.

    La plantilla de PublishIES abre los recursos con el videoclip oficial y
    pone después un tutorial por instrumento, así que el primero es el bueno.
    `None` si no hay ninguno.
    """
    m = _YOUTUBE_ID.search(getattr(page, "body", "") or "")
    if not m:
        return None
    return {"id": m.group(1), "url": f"https://www.youtube.com/watch?v={m.group(1)}"}


@register.simple_tag
def videoclip(page):
    """`{% videoclip page as video %}` para el «📺 Vídeo» del visor (fase 85)."""
    return videoclip_de(page)


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
