import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from incidencias.models import Comentario

register = template.Library()

# Un enlace termina en espacio; la puntuación final de frase no forma parte de él.
PATRON_URL = r"https?://[^\s<>\"']+[^\s<>\"'.,;:!?)\]]"
PATRON = re.compile(
    f"(?P<url>{PATRON_URL})|" + Comentario.PATRON_MENCION.pattern.replace("@(", "@(?P<usuario>", 1),
    re.IGNORECASE,
)


@register.filter
def con_menciones(comentario: Comentario) -> str:
    """Escapa el texto, conserva los saltos de línea, enlaza las URL y resalta los @usuario que existen.

    Un @ a alguien que no está en la app se queda como texto: resaltarlo diría que le ha llegado.
    Un @ dentro de una URL es parte de la URL, no una mención.
    """
    # Al autor no se le avisa de su propio comentario: su @ no se resalta.
    autor = (comentario.autor_nombre or "").strip().lower().split("@")[0]
    avisados = {c.split("@")[0] for c in comentario.correos_mencionados()} - {autor}
    texto = comentario.texto or ""
    trozos, pos = [], 0
    for m in PATRON.finditer(texto):
        trozos.append(escape(texto[pos : m.start()]))
        if m.group("url"):
            url = escape(m.group("url"))
            trozos.append(f'<a href="{url}" class="link link-primary break-all" target="_blank" rel="noopener noreferrer">{url}</a>')
        elif m.group("usuario").lower() in avisados:
            trozos.append(
                f'<span class="badge badge-sm badge-primary badge-outline font-semibold" '
                f'title="Le ha llegado este comentario por correo">@{escape(m.group("usuario"))}</span>'
            )
        else:
            trozos.append(escape(m.group(0)))
        pos = m.end()
    trozos.append(escape(texto[pos:]))
    return mark_safe("".join(trozos).replace("\n", "<br>"))  # noqa: S308 — cada trozo escapado arriba
