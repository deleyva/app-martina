"""Etiquetas de las fichas de audición (fase 111)."""

import json

from django import template

from musica.services.audicion import DISTANCIAS, etiqueta_de_cents

register = template.Library()


@register.filter
def pares_json(valor):
    """Los pares de un test audiométrico como JSON para el reproductor."""
    pares = valor.get("pares") or []
    return json.dumps(
        [{"f": float(p.get("f") or 0), "sube": bool(p.get("sube"))} for p in pares]
    )


@register.filter
def cents_legibles(cents):
    """«¼ de tono · 50 cents»."""
    try:
        return etiqueta_de_cents(float(cents))
    except (TypeError, ValueError):
        return ""


@register.simple_tag
def distancias_audicion():
    """[(clave, etiqueta)] para el selector del editor."""
    return [(clave, etiqueta_de_cents(cents)) for clave, cents, _ in DISTANCIAS]


@register.filter
def dictado_json(valor):
    """Lo que el reproductor de dictados necesita de un bloque `dictado_abc`."""
    return json.dumps(
        {
            "abc": valor.get("abc") or "",
            "tipo": valor.get("tipo") or "melodico",
            "tempo": int(valor.get("tempo") or 60),
            "timbre": valor.get("timbre") or "",
            "repeticiones": int(valor.get("repeticiones") or 2),
            "silencio": int(valor.get("silencio") if valor.get("silencio") is not None else 10),
            "cuenta_previa": bool(valor.get("cuenta_previa")),
        }
    )


@register.simple_tag
def timbres_dictado():
    """[(clave, etiqueta)] para el selector de timbre."""
    return [
        ("", "El de siempre (piano en melódicos, flauta en rítmicos)"),
        ("piano", "Piano"),
        ("epiano", "Piano eléctrico"),
        ("flauta", "Flauta"),
        ("sinte", "Sintetizador suave"),
    ]
