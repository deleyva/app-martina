"""La app se enmarca a sí misma, y con `DENY` el navegador no la deja.

El 2026-09-14 el botón de «ver la página completa» del modo presentación salía
en producción con el error del navegador dentro del modal. La causa no estaba en
la plantilla: `X_FRAME_OPTIONS = "DENY"` bloquea el marco **aunque el marco y la
página vengan del mismo dominio**.

**El fallo solo existía donde nadie lo probaba.** `local.py` pone `ALLOWALL`, así
que en desarrollo el modal funcionaba y en producción no. Por eso estos tests
miran la cabecera de la RESPUESTA y no la plantilla: la plantilla estaba bien.
"""

import pytest
from django.urls import reverse


def _enmarcable(respuesta):
    """Lo que de verdad decide si el navegador pinta el marco."""
    return respuesta.headers.get("X-Frame-Options", "").upper() != "DENY"


@pytest.mark.django_db
def test_una_pagina_del_sitio_se_puede_enmarcar(client):
    """El modo presentación mete la página del capítulo en un `iframe`. Con DENY
    el navegador se niega, y lo que se ve es su página de error."""
    respuesta = client.get("/")

    assert _enmarcable(respuesta), (
        "con X-Frame-Options: DENY el modal de «página completa» sale en blanco"
    )


@pytest.mark.django_db
def test_la_proteccion_no_se_ha_quitado(client):
    """El falsador del arreglo. Pasar de DENY a SAMEORIGIN arregla el modal;
    quitar la cabecera del todo arreglaría el modal Y abriría el clickjacking,
    y desde fuera las dos cosas se parecen."""
    respuesta = client.get("/")

    assert respuesta.headers.get("X-Frame-Options", "").upper() == "SAMEORIGIN", (
        "sin cabecera, cualquier sitio puede enmarcar la app"
    )
