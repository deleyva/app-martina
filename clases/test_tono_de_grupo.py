"""Fase 63 — Tono de clase de cada canción, por grupo. Los falsadores de C388 a C390.

El visor de ChordPro se prueba por los caminos de verdad: el contenido de un
elemento de la clase (lo que pinta la presentación) y el visor de la biblioteca
personal de un alumno. El de la biblioteca del grupo pasa `grupo_tono` igual que
la clase, y se prueba con la etiqueta.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.template import Context, Template
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Site

from clases.models import ClassSession, ClassSessionItem, Enrollment, Group, Subject, TonoDeGrupo
from martina_bescos_app.users.tests.factories import UserFactory
from musica.models import MusicLibraryIndexPage, RecursoPage

CHORDPRO = "{start_of_verse}\n[G]I found a [Em]love, for [C]me\n{end_of_verse}"

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("_hosts")]


@pytest.fixture
def _hosts(settings):
    settings.ALLOWED_HOSTS = ["*"]


@pytest.fixture
def letra():
    sitio = Site.objects.get(is_default_site=True)
    biblioteca = MusicLibraryIndexPage(title="Biblioteca", slug="biblio-tono")
    sitio.root_page.add_child(instance=biblioteca)
    biblioteca.save_revision().publish()
    cancion = RecursoPage(
        title="Perfect", slug="perfect-tono", date="2026-10-04",
        intro="x", body="<p>Cuerpo.</p>", chordpro=CHORDPRO,
    )
    biblioteca.add_child(instance=cancion)
    cancion.save_revision().publish()
    return cancion.obtener_letra_con_acordes()


def _grupo(nombre, profesor=None):
    asignatura, _ = Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})
    grupo = Group.objects.create(name=nombre, subject=asignatura, academic_year="2026-2027")
    if profesor:
        grupo.teachers.add(profesor)
    return grupo


@pytest.fixture
def profesor():
    return UserFactory(name="Profe")


@pytest.fixture
def primero(profesor):
    return _grupo("1-G-BIL", profesor)


@pytest.fixture
def cuarto(profesor):
    return _grupo("4-AC-BIL", profesor)


def _tono_en(html):
    marca = 'data-tono-grupo="'
    i = html.index(marca) + len(marca)
    return int(html[i:html.index('"', i)])


# =============================================================================
# C388 · guardar
# =============================================================================


def test_guardar_y_quitar(primero, letra, profesor):
    assert TonoDeGrupo.de(primero, letra) == 0
    assert TonoDeGrupo.guardar(primero, letra, -3, profesor) == -3
    assert TonoDeGrupo.de(primero, letra) == -3
    TonoDeGrupo.guardar(primero, letra, 2, profesor)
    assert TonoDeGrupo.objects.count() == 1 and TonoDeGrupo.de(primero, letra) == 2
    assert TonoDeGrupo.guardar(primero, letra, 0, profesor) == 0
    assert not TonoDeGrupo.objects.exists()
    with pytest.raises(ValueError):
        TonoDeGrupo.guardar(primero, letra, 12, profesor)


def test_guardar_por_la_vista_y_permisos(client, primero, cuarto, letra, profesor):
    """C388 y Anti-G: solo el profesorado del grupo, y el ChordPro no se toca."""
    url = reverse("clases:tono_de_grupo_guardar", args=[primero.pk, letra.pk])
    antes = letra.page.chordpro

    client.force_login(profesor)
    r = client.post(url, {"semitonos": "-2"})
    assert r.status_code == 200 and r.json()["semitonos"] == -2
    assert client.post(url, {"semitonos": "x"}).status_code == 400

    otro = UserFactory()
    _grupo("Otro", otro)
    client.force_login(otro)
    assert client.post(url, {"semitonos": "5"}).status_code == 404

    alumna = UserFactory()
    Enrollment.objects.create(user=alumna, group=primero)
    client.force_login(alumna)
    assert client.post(url, {"semitonos": "5"}).status_code == 302

    assert TonoDeGrupo.de(primero, letra) == -2
    letra.page.refresh_from_db()
    assert letra.page.chordpro == antes


# =============================================================================
# C389 · C390 · el visor abre en el tono del grupo
# =============================================================================


def test_en_clase_abre_en_el_tono_del_grupo(client, primero, cuarto, letra, profesor):
    """C389 (presentación) y C390 (el botón, para el profesor del grupo)."""
    TonoDeGrupo.guardar(primero, letra, 3, profesor)
    tipo = ContentType.objects.get_for_model(letra)
    client.force_login(profesor)
    for grupo, esperado in ((primero, 3), (cuarto, 0)):
        sesion = ClassSession.objects.create(
            teacher=profesor, group=grupo, date=timezone.localdate(), title="Clase"
        )
        item = ClassSessionItem.objects.create(session=sesion, content_type=tipo, object_id=letra.pk, order=0)
        html = client.get(
            reverse("clases:class_session_item_content", args=[sesion.pk, item.pk])
        ).content.decode()
        assert _tono_en(html) == esperado, grupo.name
        assert f'data-grupo="{grupo.name}"' in html
        assert reverse("clases:tono_de_grupo_guardar", args=[grupo.pk, letra.pk]) in html
        assert "{#" not in html


def test_un_alumno_de_un_solo_grupo_la_ve_en_su_tono(client, primero, cuarto, letra, profesor):
    """C389 en la biblioteca personal; sin botón de guardar para el alumnado."""
    TonoDeGrupo.guardar(primero, letra, -4, profesor)
    tipo = ContentType.objects.get_for_model(letra)
    url = reverse("my_library:view_content_object", args=[tipo.pk, letra.pk])

    de_primero = UserFactory()
    Enrollment.objects.create(user=de_primero, group=primero)
    client.force_login(de_primero)
    html = client.get(url).content.decode()
    assert _tono_en(html) == -4
    assert 'data-grupo="' not in html, "el alumnado no tiene botón de guardar"

    de_cuarto = UserFactory()
    Enrollment.objects.create(user=de_cuarto, group=cuarto)
    client.force_login(de_cuarto)
    assert _tono_en(client.get(url).content.decode()) == 0

    # Con dos grupos no se adivina: la original.
    Enrollment.objects.create(user=de_cuarto, group=primero)
    assert _tono_en(client.get(url).content.decode()) == 0


def test_la_etiqueta_usa_el_grupo_de_la_pagina(primero, letra, profesor):
    """C389 para la biblioteca del grupo, que pasa `grupo_tono` como la clase."""
    TonoDeGrupo.guardar(primero, letra, 5, profesor)
    peticion = RequestFactory().get("/")
    peticion.user = profesor
    salida = Template(
        "{% load tono_tags %}{% tono_de_clase letra as t %}{{ t.semitonos }}|{{ t.puede_guardar }}|{{ t.grupo.name }}"
    ).render(Context({"letra": letra, "request": peticion, "grupo_tono": primero}))
    assert salida == "5|True|1-G-BIL"
