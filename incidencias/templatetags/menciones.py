import re

from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe

from incidencias.models import Comentario
from incidencias.models import Incidencia
from incidencias.models import Referencia

register = template.Library()

# Un enlace termina en espacio; la puntuación final de frase no forma parte de él.
PATRON_URL = r"https?://[^\s<>\"']+[^\s<>\"'.,;:!?)\]]"
PATRON = re.compile(
    f"(?P<url>{PATRON_URL})|"
    + Comentario.PATRON_MENCION.pattern.replace("@(", "@(?P<usuario>", 1)
    + "|"
    + Referencia.PATRON.pattern.replace("#(", "#(?P<ref>", 1),
    re.IGNORECASE,
)

ICONO_ESTADO = {
    Incidencia.Estado.PENDIENTE: "⏳",
    Incidencia.Estado.EN_PROGRESO: "⚡",
    Incidencia.Estado.RESUELTA: "✅",
}


def _enlace_incidencia(incidencia: Incidencia) -> str:
    """`#123` como enlace. De una privada no se enseña el título: el texto lo lee cualquiera."""
    url = reverse("incidencias:detalle", args=[incidencia.pk])
    icono = ICONO_ESTADO.get(incidencia.estado, "")
    if incidencia.es_privada:
        titulo = "Incidencia privada"
        icono = "🔒"
    else:
        titulo = f"{incidencia.titulo} · {incidencia.get_estado_display()}"
    return (
        f'<a href="{url}" class="link link-primary font-semibold no-underline hover:underline" '
        f'title="{escape(titulo)}">#{incidencia.pk}<span class="text-xs ml-0.5">{icono}</span></a>'
    )


def _enlazar(texto: str, avisados: set[str]) -> str:
    """Escapa el texto, conserva los saltos de línea y enlaza URL, @usuario avisados y #incidencias que existen."""
    numeros = Referencia.numeros_citados(texto)
    incidencias = Incidencia.objects.in_bulk(numeros) if numeros else {}
    trozos, pos = [], 0
    for m in PATRON.finditer(texto):
        trozos.append(escape(texto[pos : m.start()]))
        if m.group("url"):
            url = escape(m.group("url"))
            trozos.append(f'<a href="{url}" class="link link-primary break-all" target="_blank" rel="noopener noreferrer">{url}</a>')
        elif m.group("ref"):
            incidencia = incidencias.get(int(m.group("ref")))
            trozos.append(_enlace_incidencia(incidencia) if incidencia else escape(m.group(0)))
        elif m.group("usuario") and m.group("usuario").lower() in avisados:
            trozos.append(
                f'<span class="badge badge-sm badge-primary badge-outline font-semibold" '
                f'title="Le ha llegado este comentario por correo">@{escape(m.group("usuario"))}</span>'
            )
        else:
            trozos.append(escape(m.group(0)))
        pos = m.end()
    trozos.append(escape(texto[pos:]))
    return mark_safe("".join(trozos).replace("\n", "<br>"))  # noqa: S308 — cada trozo escapado arriba


@register.filter
def con_menciones(comentario: Comentario) -> str:
    """Escapa el texto, conserva los saltos de línea, enlaza las URL y los #123, y resalta los @usuario que existen.

    Un @ a alguien que no está en la app se queda como texto: resaltarlo diría que le ha llegado.
    Un @ o un # dentro de una URL es parte de la URL, no una mención.
    """
    # Al autor no se le avisa de su propio comentario: su @ no se resalta.
    autor = (comentario.autor_nombre or "").strip().lower().split("@")[0]
    avisados = {c.split("@")[0] for c in comentario.correos_mencionados()} - {autor}
    return _enlazar(comentario.texto or "", avisados)


@register.filter
def con_referencias(texto: str) -> str:
    """Para la descripción: URL y #123 enlazados, sin resaltar menciones (no avisan a nadie)."""
    return _enlazar(texto or "", set())
