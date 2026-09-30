"""La raíz de apps. manda al índice de recursos; la de blogs. sigue siendo suya.

`pages/home.html` era un `{% extends "base.html" %}` sin nada dentro: la raíz
de apps.iesmartinabescos.es servía una barra de navegación y un `<main>` vacío.
Desde el 2026-09-30 redirige al índice. Lo que hay que vigilar es el otro
dominio: `smart_home_view` decide por host, y blogs. tiene que seguir cayendo
en Wagtail, no en la redirección.

En los tests el cliente se presenta como `testserver` y el Site 1 de Django es
`example.com`, así que `client.get("/")` a secas es el caso blogs. Para probar
el caso apps. se pone el dominio del Site 1 a `testserver`.
"""

import pytest
from django.conf import settings
from django.contrib.sites.models import Site

INDICE = "/indice-de-recursos-musicales/"


def _hacer_que_testserver_sea_apps():
    Site.objects.filter(pk=settings.SITE_ID).update(domain="testserver")


@pytest.mark.django_db
def test_la_raiz_de_apps_redirige_al_indice(client):
    _hacer_que_testserver_sea_apps()

    respuesta = client.get("/")

    assert respuesta.status_code == 302, "un 301 lo cachea el navegador; queremos poder deshacerlo"
    assert respuesta["Location"] == INDICE


@pytest.mark.django_db
def test_la_redireccion_conserva_el_idioma(client):
    _hacer_que_testserver_sea_apps()

    respuesta = client.get("/?lang=en")

    assert respuesta["Location"] == INDICE + "?lang=en"


@pytest.mark.django_db
def test_la_raiz_de_otro_dominio_no_redirige(client):
    """El caso blogs.: el host no es el del Site 1, así que Wagtail sirve su
    propia raíz. Si esto redirigiera, la portada de los blogs desaparecería."""
    respuesta = client.get("/")

    assert respuesta.status_code != 302 or respuesta["Location"] != INDICE
