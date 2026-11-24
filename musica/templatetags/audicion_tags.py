"""Etiquetas de las fichas: audición (fase 111) y patrones de piano (fases 114 y 115)."""

import json

from django import template

from musica.services import patrones
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
def ejercicios_a_pintar(ficha, solo=None):
    """`[(bloque, numero)]` de la ficha, o solo el del bloque `solo` (fase 112).

    Con `solo` y el bloque ya borrado devuelve una lista vacía, y el parcial lo
    dice; nunca cae a la ficha entera, que es justo lo que no se quiere ver.
    """
    ejercicios = ficha.ejercicios()
    if not solo:
        return ejercicios
    return [(b, n) for b, n in ejercicios if n and b.id == solo]


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


# --- Patrones de piano (fases 114 y 115) ---------------------------------------


@register.filter
def patron_json(valor):
    """Lo que el navegador necesita de un bloque `patron_piano`: grados, no notas."""
    return json.dumps(patrones.para_el_navegador(valor))


@register.filter
def progresion_legible(valor):
    """«I – V – V – I», o «i – v – iv – i» en una menor; vacío si no se entiende."""
    return patrones.progresion_legible(valor)


@register.filter
def nombre_del_patron(clave):
    return patrones.nombre_del_patron(clave) or clave


@register.simple_tag
def patrones_de_piano():
    """[(id, nombre)] para el desplegable, de más fácil a más difícil."""
    return patrones.patrones()


@register.simple_tag
def tonalidades_de_piano(como=None):
    """[(id, nombre)] para el desplegable de quien mira.

    Con `como` (la tonalidad del patrón), solo las de su modo: transportar no
    cambia una progresión menor en una mayor.
    """
    return patrones.tonalidades(patrones.modo_de(como) if como else None)


@register.simple_tag
def tonalidades_de_piano_por_modo():
    """[("Mayores", [(id, nombre), …]), ("Menores", […])] para el desplegable del editor."""
    return patrones.tonalidades_por_modo()
