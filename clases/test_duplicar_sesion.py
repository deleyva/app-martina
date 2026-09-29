# ruff: noqa: S101
"""Duplicar una clase no puede perder de dónde salió cada elemento.

El fallo, medido en producción el 2026-09-29: la copia de una clase pintaba la
tablatura sin el botón de Songsterr, y sin el de «ver la página entera». El
enlace a Songsterr no vive en el .gp sino en la `RecursoPage`, y a ella solo se
llega por `source_page`, que `class_session_duplicate` no copiaba.
"""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from wagtail.documents.models import Document
from wagtail.models import Page

from clases.models import ClassSession
from clases.models import ClassSessionItem
from clases.models import Group
from clases.models import Subject
from martina_bescos_app.users.tests.factories import UserFactory
from musica.models import RecursoPage

SONGSTERR = "https://www.songsterr.com/a/wsa/lynyrd-skynyrd-sweet-home-alabama-tab-s456"


@pytest.fixture
def profe(db):
    return UserFactory(is_staff=True)


@pytest.fixture
def sesion(db, profe):
    materia, _ = Subject.objects.get_or_create(code="MUS", defaults={"name": "Música"})
    grupo = Group.objects.create(name="4AG", subject=materia)
    grupo.teachers.add(profe)
    return ClassSession.objects.create(
        teacher=profe, group=grupo, date="2026-09-29", title="Backbeat",
    )


@pytest.fixture
def tablatura(db, sesion):
    """Un .gp dentro de la clase, llegado desde la página de su canción."""
    cancion = RecursoPage(
        title="Sweet Home Alabama",
        slug="sweet-home-alabama",
        date="2026-09-29",
        intro="x",
        songsterr_url=SONGSTERR,
    )
    Page.objects.get(id=2).add_child(instance=cancion)
    cancion.save_revision().publish()

    gp = Document.objects.create(title="Sweet Home Alabama", file="documents/sweet.gp")
    return ClassSessionItem.objects.create(
        session=sesion,
        content_type=ContentType.objects.get_for_model(Document),
        object_id=gp.pk,
        source_page=cancion,
        order=0,
    )


def _duplicar(client, profe, sesion):
    client.force_login(profe)
    client.post(reverse("clases:class_session_duplicate", args=[sesion.pk]))
    return ClassSession.objects.exclude(pk=sesion.pk).get()


def test_la_copia_conserva_la_pagina_de_origen(client, profe, sesion, tablatura):
    copia = _duplicar(client, profe, sesion)

    item = copia.items.get()
    assert item.source_page_id == tablatura.source_page_id
    assert item.songsterr_link == {"url": SONGSTERR, "exacto": True}


def test_la_tablatura_de_la_copia_lleva_el_boton_de_songsterr(
    client, profe, sesion, tablatura,
):
    """El falsador de verdad: el HTML que la clase pide para ese elemento."""
    copia = _duplicar(client, profe, sesion)

    url = reverse(
        "clases:class_session_item_content", args=[copia.pk, copia.items.get().pk],
    )
    html = client.get(url).content.decode()

    assert 'id="gp-songsterr"' in html
    assert SONGSTERR in html


def test_el_comando_devuelve_la_pagina_a_las_copias_antiguas(sesion, tablatura):
    """Las copias hechas antes del arreglo: el dato sigue en la original."""
    from django.core.management import call_command

    copia = ClassSession.objects.create(
        teacher=sesion.teacher, group=sesion.group, date="2026-09-30", title="Copia",
    )
    huerfano = ClassSessionItem.objects.create(
        session=copia,
        content_type=tablatura.content_type,
        object_id=tablatura.object_id,
        order=0,
    )

    call_command("recuperar_origen_de_copias")
    huerfano.refresh_from_db()
    assert huerfano.source_page_id is None  # el ensayo no escribe

    call_command("recuperar_origen_de_copias", "--aplicar")
    huerfano.refresh_from_db()
    assert huerfano.source_page_id == tablatura.source_page_id
