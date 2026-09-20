"""Fase 37 — El desplegable por capítulos al montar la sesión. C201 y C204.

Lo que se prueba aquí es la pantalla, no el motor: que el desplegable exista,
que traiga los capítulos con sus elementos marcables, y que **no** viaje en la
primera carga. Lo segundo importa tanto como lo primero: un cuarto de ESO tiene
siete libros de más de doscientos elementos, y enumerarlos al abrir la sesión
sería recorrerlos todos para mirar, casi siempre, ninguno.
"""

import pytest
from django.urls import reverse

from clases import libros_de_grupo
from clases.models import ClassSession, Group, GroupBook, Subject
from martina_bescos_app.users.tests.factories import UserFactory
from my_library.tests import _libro_con_capitulos


@pytest.fixture
def profesor(db):
    return UserFactory(is_staff=True)


@pytest.fixture
def group_book(db, profesor):
    asignatura, _ = Subject.objects.get_or_create(code="MUS", defaults={"name": "Música"})
    grupo = Group.objects.create(name="4-AC-BIL", subject=asignatura)
    grupo.teachers.add(profesor)
    libro, _ = _libro_con_capitulos(
        "Historia de la música moderna",
        "historia-moderna",
        [("Los años cincuenta", ["cartel", "foto"]), ("Los sesenta", ["portada"])],
    )
    return GroupBook.objects.create(group=grupo, libro=libro, seccion="teoria")


@pytest.fixture
def sesion(db, profesor, group_book):
    return ClassSession.objects.create(
        teacher=profesor, group=group_book.group, date="2026-09-21", title="Clase"
    )


def test_la_vista_previa_no_enumera_el_libro(client, profesor, sesion, group_book):
    """C204. El falsador del coste: si el segundo elemento del capítulo sale en
    la primera carga, es que se ha enumerado el libro entero para pintarla."""
    client.force_login(profesor)

    html = client.get(
        reverse("clases:class_session_prepare_preview", args=[sesion.pk])
    ).content.decode()

    assert "cartel" in html, "lo propuesto sí sale"
    assert "foto" not in html, "lo demás del capítulo, no"
    assert "Los sesenta" not in html, "ni los otros capítulos"
    assert "Elegir más de" in html, "pero la puerta está"


def test_el_desplegable_trae_los_capitulos_con_sus_elementos(
    client, profesor, sesion, group_book
):
    """C201. Capítulos del libro, cada uno con sus elementos marcables."""
    client.force_login(profesor)

    html = client.get(
        reverse("clases:class_session_book_picker", args=[sesion.pk]),
        {"group_book": group_book.pk},
    ).content.decode()

    assert "Los años cincuenta" in html
    assert "Los sesenta" in html
    assert 'name="elementos"' in html
    # Y las casillas llevan la clave que el formulario sabe leer.
    filas = {f["titulo"]: f for f in libros_de_grupo.enumerar(group_book)}
    esperada = (
        f'{group_book.pk}:{filas["foto"]["tipo"].pk}:{filas["foto"]["objeto"].pk}'
    )
    assert esperada in html


def test_lo_propuesto_arriba_no_se_ofrece_dos_veces(
    client, profesor, sesion, group_book
):
    """La misma casilla dos veces en la misma pantalla confunde y duplica."""
    client.force_login(profesor)
    filas = {f["titulo"]: f for f in libros_de_grupo.enumerar(group_book)}
    propuesto = f'{filas["cartel"]["tipo"].pk}:{filas["cartel"]["objeto"].pk}'

    html = client.get(
        reverse("clases:class_session_book_picker", args=[sesion.pk]),
        {"group_book": group_book.pk, "propuesto": propuesto},
    ).content.decode()

    assert "propuesto arriba" in html
    assert f'value="{group_book.pk}:{propuesto}"' not in html


def test_el_libro_de_otro_grupo_no_se_abre(client, profesor, sesion, db):
    """La pk del libro viaja en la URL, y una URL la escribe cualquiera."""
    asignatura, _ = Subject.objects.get_or_create(code="MUS", defaults={"name": "Música"})
    otro = Group.objects.create(name="Otro", subject=asignatura)
    libro, _ = _libro_con_capitulos("Ajeno", "ajeno-picker", [("C1", ["x1"])])
    ajeno = GroupBook.objects.create(group=otro, libro=libro, seccion="teoria")
    client.force_login(profesor)

    respuesta = client.get(
        reverse("clases:class_session_book_picker", args=[sesion.pk]),
        {"group_book": ajeno.pk},
    )

    assert respuesta.status_code == 404


def test_el_formulario_mete_lo_marcado(client, profesor, sesion, group_book):
    """C200 de punta a punta: lo que se envía marcado es lo que entra."""
    client.force_login(profesor)
    filas = {f["titulo"]: f for f in libros_de_grupo.enumerar(group_book)}
    claves = [
        f'{group_book.pk}:{filas[t]["tipo"].pk}:{filas[t]["objeto"].pk}'
        for t in ("cartel", "portada")
    ]

    client.post(
        reverse("clases:class_session_prepare", args=[sesion.pk]),
        {"elementos": claves},
    )

    assert [i.content_object.title for i in sesion.items.order_by("order")] == [
        "cartel",
        "portada",
    ]


def test_un_libro_sin_nada_pendiente_conserva_su_desplegable(
    client, profesor, sesion, group_book
):
    """«Un desplegable por capítulo de CADA libro», también del terminado.

    Un libro cuyo siguiente ya está en la clase desaparece de la propuesta. Si
    con él se fuera su desplegable, sus capítulos dejarían de ser alcanzables
    justo cuando más falta hace cogerlos a mano.
    """
    client.force_login(profesor)
    filas = libros_de_grupo.enumerar(group_book)
    # Todo el libro dado por visto: ya no propone nada.
    for fila in filas:
        libros_de_grupo.excepcion(
            group_book,
            fila["objeto"],
            capitulo=fila["capitulo"],
            estado="visto",
        )

    html = client.get(
        reverse("clases:class_session_prepare_preview", args=[sesion.pk])
    ).content.decode()

    assert "Sin nada pendiente que proponer" in html
    assert "Elegir de «Historia de la música moderna»" in html
