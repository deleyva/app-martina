"""Tratado o saltado en clase: qué se trabajó de verdad de lo preparado (fase 68).

Pedido de Jesús el 2026-10-06: al preparar mete más material del que da tiempo
a dar, y lo que no llega a ver se queda en la sesión como si se hubiera dado.
Quiere marcar, al pasar de elemento, si lo trabajó o se lo saltó, y ver al
preparar cuántas veces lo ha trabajado de verdad.

Las afirmaciones que hay que falsar:

- **No se mezcla con el visto.** Marcar tratado no da por visto ni toca el
  libro, y dar por visto no marca tratado. Fue condición explícita.
- **El recuento cuenta lo tratado, por grupo**, y no lo metido en una sesión ni
  lo que se quedó sin marcar.
"""

import json
import re
from datetime import date

import pytest
from django.urls import reverse

from clases import libros_de_grupo
from clases.models import ClassSession, ClassSessionItem, GroupBook, GroupBookItem
from clases.test_marcas_preparar import _grupo
from my_library.tests import _libro_con_capitulos


@pytest.fixture
def profesor(django_user_model):
    return django_user_model.objects.create_user(email="profe@x.es", password="x")


@pytest.fixture
def montaje(db, profesor):
    """Un libro de tres elementos en dos grupos del mismo profesor."""
    libro, _ = _libro_con_capitulos(
        "Método", "metodo-tratado", [("Capítulo 1", ["a1", "a2", "a3"])]
    )
    grupo = _grupo(profesor, "3-FH")
    otro = _grupo(profesor, "3-EA")
    gb = GroupBook.objects.create(group=grupo, libro=libro, seccion="teoria")
    gb_otro = GroupBook.objects.create(group=otro, libro=libro, seccion="teoria")
    return {"grupo": grupo, "otro": otro, "gb": gb, "gb_otro": gb_otro}


def _sesion_con(profesor, grupo, group_book, cuantos=3):
    sesion = ClassSession.objects.create(
        teacher=profesor, group=grupo, date=date(2026, 10, 6), title="Clase"
    )
    for orden, fila in enumerate(libros_de_grupo.enumerar(group_book)[:cuantos]):
        ClassSessionItem.objects.create(
            session=sesion,
            content_type=fila["tipo"],
            object_id=fila["objeto"].pk,
            source_page=fila["capitulo"],
            group_book=group_book,
            seccion=group_book.seccion,
            order=orden,
        )
    return sesion


def _tratar(client, item, valor):
    return client.post(
        reverse("clases:class_session_item_tratado", args=[item.pk]), {"valor": valor}
    )


def test_marcar_tratado_saltado_y_sin_marcar(client, montaje, profesor):
    client.force_login(profesor)
    item = _sesion_con(profesor, montaje["grupo"], montaje["gb"]).items.first()
    assert item.tratado is None

    for valor, esperado in [("si", True), ("no", False), ("", None)]:
        r = _tratar(client, item, valor)
        assert r.status_code == 200
        item.refresh_from_db()
        assert item.tratado is esperado


def test_tratado_no_toca_el_visto_ni_el_libro(client, montaje, profesor):
    """Condición explícita de Jesús: los dos estados no se mezclan."""
    client.force_login(profesor)
    item = _sesion_con(profesor, montaje["grupo"], montaje["gb"]).items.first()

    _tratar(client, item, "si")
    item.refresh_from_db()
    assert item.visto is False
    assert not GroupBookItem.objects.filter(group_book=montaje["gb"]).exists()
    # Lo tratado sigue proponiéndose: trabajarlo hoy no es «no me lo vuelvas a dar».
    assert [f["titulo"] for f in libros_de_grupo.previsualizar_sesion(montaje["grupo"])] == ["a1"]

    # Y al revés: dar por visto no marca tratado.
    client.post(reverse("clases:class_session_item_visto", args=[item.pk]))
    item.refresh_from_db()
    assert item.visto is True
    assert item.tratado is True  # lo que había, intacto

    otro = item.session.items.exclude(pk=item.pk).first()
    client.post(reverse("clases:class_session_item_visto", args=[otro.pk]))
    otro.refresh_from_db()
    assert otro.visto is True and otro.tratado is None


def test_recuento_cuenta_lo_tratado_por_grupo(client, montaje, profesor):
    client.force_login(profesor)
    # Dos clases de 3-FH con los tres elementos: a1 tratado dos veces, a2
    # saltado una y tratado otra, a3 nunca marcado.
    s1 = _sesion_con(profesor, montaje["grupo"], montaje["gb"])
    s2 = _sesion_con(profesor, montaje["grupo"], montaje["gb"])
    i1 = list(s1.items.order_by("order"))
    i2 = list(s2.items.order_by("order"))
    _tratar(client, i1[0], "si")
    _tratar(client, i2[0], "si")
    _tratar(client, i1[1], "no")
    _tratar(client, i2[1], "si")
    # En el otro grupo, a1 tratado: no puede sumar en 3-FH.
    s3 = _sesion_con(profesor, montaje["otro"], montaje["gb_otro"])
    _tratar(client, s3.items.order_by("order").first(), "si")

    recuento = libros_de_grupo.recuento_en_clase(montaje["grupo"])
    clave = lambda it: (it.content_type_id, it.object_id)  # noqa: E731
    assert recuento[clave(i1[0])] == {"tratado": 2, "saltado": 0}
    assert recuento[clave(i1[1])] == {"tratado": 1, "saltado": 1}
    assert clave(i1[2]) not in recuento  # metido en dos clases, nunca marcado

    assert libros_de_grupo.recuento_en_clase(montaje["otro"])[clave(i1[0])] == {
        "tratado": 1,
        "saltado": 0,
    }


def test_preparar_ensena_el_recuento(client, montaje, profesor):
    client.force_login(profesor)
    anterior = _sesion_con(profesor, montaje["grupo"], montaje["gb"], cuantos=1)
    _tratar(client, anterior.items.first(), "si")
    nueva = ClassSession.objects.create(
        teacher=profesor, group=montaje["grupo"], date=date(2026, 10, 8), title="Otra"
    )

    html = client.get(
        reverse("clases:class_session_prepare_preview", args=[nueva.pk])
    ).content.decode()
    assert "Tratado en clase 1 vez con este grupo" in html
    assert "✓1" in html

    # Los «Y después» también lo llevan, y a2 no tiene nada que contar.
    filas = libros_de_grupo.enumerar(montaje["gb"])
    html = client.get(
        reverse("clases:class_session_book_next", args=[nueva.pk]),
        {"group_book": montaje["gb"].pk, "propuesto": f"{filas[1]['tipo'].pk}:{filas[1]['objeto'].pk}"},
    ).content.decode()
    assert "Tratado en clase 1 vez" in html  # a1, tratado; ya no es lo propuesto


def test_otro_profesor_no_puede_marcar(client, montaje, profesor, django_user_model):
    item = _sesion_con(profesor, montaje["grupo"], montaje["gb"]).items.first()
    intruso = django_user_model.objects.create_user(email="otro@x.es", password="x")
    _grupo(intruso, "1-A")
    client.force_login(intruso)
    r = _tratar(client, item, "si")
    assert r.status_code in (302, 403, 404)
    item.refresh_from_db()
    assert item.tratado is None


def test_el_visor_lleva_el_tratado_y_la_pregunta(client, montaje, profesor):
    client.force_login(profesor)
    sesion = _sesion_con(profesor, montaje["grupo"], montaje["gb"])
    _tratar(client, sesion.items.order_by("order").first(), "no")

    html = client.get(reverse("clases:class_session_present", args=[sesion.pk])).content.decode()
    playlist = json.loads(re.search(r"var playlist = (\[.*?\]);\n", html).group(1))
    assert [p["tratado"] for p in playlist] == [False, None, None]
    assert 'id="pregunta-tratado"' in html
