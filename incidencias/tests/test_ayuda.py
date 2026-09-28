# ruff: noqa: PLR2004
"""«¿A quién va cada cosa?» es pública y lee de la base de datos."""

import pytest
from django.test import Client
from django.urls import reverse

from incidencias.tests.factories import ServicioFactory


@pytest.mark.django_db
def test_publica_sin_sesion_200():
    r = Client().get(reverse("incidencias:ayuda"))
    assert r.status_code == 200
    assert "¿A quién va cada incidencia?" in r.content.decode()


@pytest.mark.django_db
def test_lista_servicios_activos_desde_bd():
    ServicioFactory(nombre="Redes y conectividad", correos="redes@example.com", telefono="976 000 111")
    html = Client().get(reverse("incidencias:ayuda")).content.decode()
    assert "Redes y conectividad" in html
    assert "redes@example.com" in html
    assert "976 000 111" in html


@pytest.mark.django_db
def test_inactivo_no_aparece():
    ServicioFactory(nombre="Servicio muerto", activo=False)
    html = Client().get(reverse("incidencias:ayuda")).content.decode()
    assert "Servicio muerto" not in html
