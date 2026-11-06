"""Fase 103 — la ayuda separada por público. Falsadores de C697 y C698."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import Group as GrupoDePermisos
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from wagtail.models import Page

from clases.models import Enrollment, Group, Subject
from cms.models import HelpGuidePage, HelpIndexPage
from martina_bescos_app.users.permisos import GRUPO_PROFESORADO
from martina_bescos_app.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

PROFE = "Calificar de principio a fin"
OTRA_PROFE = "Turnos de la banda de prueba"
ALUMNO = "Guía del alumnado"


@pytest.fixture
def indice():
    raiz = Page.get_first_root_node()
    indice = raiz.add_child(instance=HelpIndexPage(title="Ayuda de prueba", slug="ayuda-de-prueba"))
    for titulo, publico in ((PROFE, "profesorado"), (ALUMNO, "alumnado"), (OTRA_PROFE, "profesorado")):
        indice.add_child(instance=HelpGuidePage(title=titulo, slug=titulo.lower().replace(" ", "-"), publico=publico))
    return indice


def _pintar(pagina, user):
    request = RequestFactory().get("/")
    request.user = user
    SessionMiddleware(lambda r: None).process_request(request)
    request._messages = FallbackStorage(request)
    return pagina.serve(request).render().content.decode()


def _profesor():
    user = UserFactory()
    user.groups.add(GrupoDePermisos.objects.get_or_create(name=GRUPO_PROFESORADO)[0])
    return user


def _alumno():
    user = UserFactory()
    asignatura, _ = Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})
    grupo = Group.objects.create(name="1-A", subject=asignatura, academic_year="2026-2027")
    Enrollment.objects.create(user=user, group=grupo)
    return user


def test_por_defecto_una_guia_es_de_profesorado():
    assert HelpGuidePage().publico == HelpGuidePage.PROFESORADO


def test_el_profesor_ve_sus_guias_primero_y_luego_las_del_alumnado(indice):
    html = _pintar(indice, _profesor())
    assert 'id="profesorado"' in html and 'id="alumnado"' in html
    assert html.index('id="profesorado"') < html.index('id="alumnado"')
    # Dentro de su sección, por el orden del árbol.
    assert html.index(PROFE) < html.index(OTRA_PROFE) < html.index(ALUMNO)
    assert "{#" not in html


@pytest.mark.parametrize("quien", ["alumno", "anonimo"])
def test_el_alumnado_y_quien_no_ha_entrado_solo_ven_las_suyas(indice, quien):
    user = _alumno() if quien == "alumno" else AnonymousUser()
    html = _pintar(indice, user)
    assert ALUMNO in html
    assert PROFE not in html and OTRA_PROFE not in html
    assert 'id="profesorado"' not in html


def test_una_guia_de_profesorado_se_abre_por_su_enlace_sin_ser_profesor(indice):
    guia = HelpGuidePage.objects.get(title=PROFE)
    html = _pintar(guia, _alumno())
    assert PROFE in html
