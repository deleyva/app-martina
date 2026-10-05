from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from incidencias.models import Comentario

register = template.Library()


@register.filter
def con_menciones(comentario: Comentario) -> str:
    """Escapa el texto, conserva los saltos de línea y resalta los @usuario que existen.

    Un @ a alguien que no está en la app se queda como texto: resaltarlo diría que le ha llegado.
    """
    avisados = {c.split("@")[0] for c in comentario.correos_mencionados()}
    seguro = escape(comentario.texto or "")

    def resaltar(m):
        if m.group(1).lower() not in avisados:
            return m.group(0)
        return (
            f'<span class="badge badge-sm badge-primary badge-outline font-semibold" '
            f'title="Le ha llegado este comentario por correo">@{m.group(1)}</span>'
        )

    return mark_safe(Comentario.PATRON_MENCION.sub(resaltar, seguro).replace("\n", "<br>"))  # noqa: S308 — escapado arriba
