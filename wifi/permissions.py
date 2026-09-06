"""Quién puede pedir y quién puede gestionar.

El proyecto **no** tiene ningún marcador de rol en `User` — solo `es_tecnico`,
que es de incidencias. La única señal disponible para separar personal de
alumnado es la convención de cuentas del centro, la misma que asoma en los
`placeholder` de `incidencias/forms.py`: `eromero` para personal, `0125eromero`
para alumnado (prefijo numérico de promoción).

Es una heurística, y va a fallar en algún caso, así que hay dos válvulas:
el patrón es configurable por entorno, y un grupo de Django autoriza a mano
las excepciones.
"""

from __future__ import annotations

import re

from django.conf import settings

GRUPO_GESTION = "Gestión WiFi"
GRUPO_PERSONAL = "WiFi personal autorizado"


def _grupos(user) -> set[str]:
    if not getattr(user, "is_authenticated", False):
        return set()
    return set(user.groups.values_list("name", flat=True))


def es_gestor(user) -> bool:
    """¿Puede entrar en la pantalla de gestión (los «administrativos»)?"""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return GRUPO_GESTION in _grupos(user)


def _dominios_permitidos() -> set[str]:
    dominios = {getattr(settings, "DEFAULT_USER_EMAIL_DOMAIN", "").strip().lower()}
    dominios |= {
        d.strip().lower()
        for d in getattr(settings, "WIFI_DOMINIOS_EXTRA", [])
        if d.strip()
    }
    return {d for d in dominios if d}


def puede_solicitar(user) -> bool:
    """¿Es personal del centro, y por tanto puede pedir el alta?"""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or es_gestor(user):
        return True

    grupos = _grupos(user)
    if GRUPO_PERSONAL in grupos:
        return True

    correo = (user.email or "").strip().lower()
    if "@" not in correo:
        return False
    local, _, dominio = correo.partition("@")

    dominios = _dominios_permitidos()
    if dominios and dominio not in dominios:
        return False

    patron = getattr(settings, "WIFI_PATRON_PERSONAL", r"^[a-z]")
    return bool(re.match(patron, local, flags=re.IGNORECASE))
