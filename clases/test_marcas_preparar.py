"""Marcar visto o para casa al PREPARAR la clase, sin pasar por la clase.

Nace de una petición del principal del 2026-09-22: el motor propone lo siguiente
pendiente de cada libro, y hasta ahora la única forma de decirle «esto ya está,
no me lo vuelvas a ofrecer» era meterlo en una sesión y darlo por visto allí.
Con varios grupos a ritmos distintos eso obliga a pasar por clase material que
no se va a dar.

La afirmación que de verdad hay que falsar no es «se guarda la fila», sino **«lo
marcado deja de proponerse»**, y además **por grupo**: dos grupos sobre el mismo
libro tienen que poder ir por sitios distintos. Los dos tests que lo comprueban
son los únicos montajes capaces de refutarlo.

Los ayudantes de construcción de libros son los de `my_library.tests`, igual que
en `test_libros_de_grupo`: contra libros de mentira esto pasaría siempre.
"""

import pytest
from django.urls import reverse

from clases import libros_de_grupo
from clases.models import Group, GroupBook, GroupBookItem, Subject
from my_library.tests import _libro_con_capitulos


@pytest.fixture
def profesor(django_user_model):
    return django_user_model.objects.create_user(email="profe@x.es", password="x")


def _grupo(profesor, nombre="3-FH"):
    asignatura, _ = Subject.objects.get_or_create(
        name="Música", defaults={"code": "MUS"}
    )
    grupo = Group.objects.create(
        name=nombre, subject=asignatura, academic_year="2026-2027"
    )
    grupo.teachers.add(profesor)
    return grupo


@pytest.fixture
def montaje(db, profesor):
    """Un libro de tres elementos asignado a un grupo del profesor."""
    libro, _ = _libro_con_capitulos(
        "Método", "metodo-marcas", [("Capítulo 1", ["a1", "a2", "a3"])]
    )
    grupo = _grupo(profesor)
    group_book = GroupBook.objects.create(group=grupo, libro=libro, seccion="teoria")
    filas = libros_de_grupo.enumerar(group_book)
    return {"libro": libro, "grupo": grupo, "gb": group_book, "filas": filas}


def _marcar(client, group_book, fila, campo):
    return client.post(
        reverse("clases:preparar_marca", args=[group_book.pk]),
        {
            "content_type": fila["tipo"].pk,
            "object_id": fila["objeto"].pk,
            "campo": campo,
        },
    )


def _titulos_propuestos(grupo):
    return [f["titulo"] for f in libros_de_grupo.previsualizar_sesion(grupo)]


def test_lo_marcado_como_visto_deja_de_proponerse(client, montaje, profesor):
    """La razón de ser de todo esto."""
    client.force_login(profesor)
    assert _titulos_propuestos(montaje["grupo"]) == ["a1"]

    _marcar(client, montaje["gb"], montaje["filas"][0], "visto")

    assert _titulos_propuestos(montaje["grupo"]) == ["a2"]


def test_se_pueden_saltar_varios_de_una_vez(client, montaje, profesor):
    """Universal, no de ejemplo: marcar los dos primeros propone el tercero."""
    client.force_login(profesor)

    for fila in montaje["filas"][:2]:
        _marcar(client, montaje["gb"], fila, "visto")

    assert _titulos_propuestos(montaje["grupo"]) == ["a3"]


def test_la_decision_es_de_cada_grupo(client, montaje, profesor, django_user_model):
    """C126 otra vez, por la puerta nueva: dos grupos sobre el MISMO libro.

    Es el único montaje capaz de refutar que el avance sea por grupo. Si la
    marca se guardara contra el libro y no contra el `GroupBook`, el segundo
    grupo perdería el elemento sin que nadie lo tocara.
    """
    client.force_login(profesor)
    otro = _grupo(profesor, "3-EA")
    GroupBook.objects.create(group=otro, libro=montaje["libro"], seccion="teoria")

    _marcar(client, montaje["gb"], montaje["filas"][0], "visto")

    assert _titulos_propuestos(montaje["grupo"]) == ["a2"]
    assert _titulos_propuestos(otro) == ["a1"]


def test_marcar_es_reversible(client, montaje, profesor):
    """En una pantalla de preparar se dan toques por error."""
    client.force_login(profesor)
    fila = montaje["filas"][0]

    _marcar(client, montaje["gb"], fila, "visto")
    _marcar(client, montaje["gb"], fila, "visto")

    assert _titulos_propuestos(montaje["grupo"]) == ["a1"]


def test_la_casita_se_guarda_sin_dar_por_visto(client, montaje, profesor):
    """Son dos decisiones distintas: «ya está» y «se lo llevan»."""
    client.force_login(profesor)
    fila = montaje["filas"][0]

    _marcar(client, montaje["gb"], fila, "a_casa")

    item = GroupBookItem.objects.get(
        group_book=montaje["gb"], content_type=fila["tipo"], object_id=fila["objeto"].pk
    )
    assert item.a_casa is True
    assert item.estado == GroupBookItem.PENDIENTE
    assert _titulos_propuestos(montaje["grupo"]) == ["a1"]


def test_un_profesor_no_marca_en_el_libro_de_otro(
    client, montaje, django_user_model
):
    """La puerta, probada por HTTP: es donde estaría el agujero."""
    intruso = django_user_model.objects.create_user(email="otro@x.es", password="x")
    _grupo(intruso, "1-A")  # profesor de verdad, pero de otro grupo
    client.force_login(intruso)

    r = _marcar(client, montaje["gb"], montaje["filas"][0], "visto")

    assert r.status_code == 404
    assert not GroupBookItem.objects.filter(group_book=montaje["gb"]).exists()


def test_quien_no_es_profesor_no_marca(client, montaje, django_user_model):
    alumno = django_user_model.objects.create_user(email="alumna@x.es", password="x")
    client.force_login(alumno)

    r = _marcar(client, montaje["gb"], montaje["filas"][0], "visto")

    assert r.status_code != 200
    assert not GroupBookItem.objects.filter(group_book=montaje["gb"]).exists()
