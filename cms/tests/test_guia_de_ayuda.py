"""La guía de ayuda numera solo los pasos: un aviso en medio no se lleva número.

Pasó en la guía de la banda (2026-11-01): con un aviso entre el paso 3 y el 4,
la plantilla saltaba del 3 al 5 mientras la cabecera decía «8 pasos».
"""

import json

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from wagtail.models import Page

from cms.models import HelpGuidePage
from cms.models import HelpIndexPage

pytestmark = pytest.mark.django_db


def _guia():
    raiz = Page.get_first_root_node()
    indice = raiz.add_child(instance=HelpIndexPage(title="Ayuda de prueba", slug="ayuda-de-prueba"))
    bloques = [
        {"type": "paso", "value": {"titulo": "Primero", "texto": "<p>uno</p>", "captura": None, "pie": ""}},
        {"type": "aviso", "value": {"texto": "<p>Ojo con esto</p>"}},
        {"type": "paso", "value": {"titulo": "Segundo", "texto": "<p>dos</p>", "captura": None, "pie": ""}},
    ]
    return indice.add_child(
        instance=HelpGuidePage(title="Guía de prueba", slug="guia-de-prueba", pasos=json.dumps(bloques))
    )


def test_los_avisos_no_llevan_numero():
    guia = _guia()
    assert [n for n, _ in guia.bloques_numerados] == [1, None, 2]
    assert guia.numero_de_pasos == 2


def test_la_pagina_numera_1_y_2_con_un_aviso_en_medio():
    guia = _guia()
    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    SessionMiddleware(lambda r: None).process_request(request)
    request._messages = FallbackStorage(request)
    html = guia.serve(request).render().content.decode()
    numeros = [
        trozo.split("</span>")[0].strip()
        for trozo in html.split('badge badge-primary badge-lg shrink-0 mt-1">')[1:]
    ]
    assert numeros == ["1", "2"]
    assert "Ojo con esto" in html
    assert "{#" not in html
