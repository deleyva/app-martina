"""Fase 61 — Lista de lectura del profesor. Los falsadores de C360 a C366.

Los libros son de verdad (`my_library.tests`), como en el resto de `clases`: un
libro de mentira pasaría los tests y fallaría con los reales.
"""

from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from clases import lectura
from clases.models import (
    ClassSession,
    ClassSessionItem,
    Group,
    GroupBook,
    GroupBookItem,
    LibroOcultoEnLectura,
    Subject,
)
from my_library.models import LibraryItem
from my_library.tests import _libro_con_capitulos

HOY = timezone.localdate()


# =============================================================================
# Montaje
# =============================================================================


def _grupo(nombre, *profesores):
    asignatura, _ = Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})
    grupo = Group.objects.create(name=nombre, subject=asignatura, academic_year="2026-2027")
    for p in profesores:
        grupo.teachers.add(p)
    return grupo


def _sesion(grupo, profesor, dias, objetos, capitulo=None, visto=False):
    """Una sesión a `dias` de hoy (negativo = pasada) con `objetos` dentro."""
    sesion = ClassSession.objects.create(
        teacher=profesor, group=grupo, date=HOY + timedelta(days=dias), title=f"Clase {dias}"
    )
    for n, objeto in enumerate(objetos):
        ClassSessionItem.objects.create(
            session=sesion,
            content_type=ContentType.objects.get_for_model(objeto),
            object_id=objeto.pk,
            source_page=capitulo,
            order=n,
            visto=visto,
        )
    return sesion


@pytest.fixture
def profesor(django_user_model):
    return django_user_model.objects.create_user(email="profe@example.com", password="x")


@pytest.fixture
def otro_profesor(django_user_model):
    return django_user_model.objects.create_user(email="otra@example.com", password="x")


@pytest.fixture
def libro(db):
    """Un libro de 5 imágenes en dos capítulos."""
    return _libro_con_capitulos(
        "Método", "metodo-lectura", [("Cap 1", ["a1", "a2", "a3"]), ("Cap 2", ["b1", "b2"])]
    )


def _titulos(datos):
    return [e["titulo"] for e in datos["elementos"]]


def _chips(datos, titulo):
    fila = next(e for e in datos["elementos"] if e["titulo"] == titulo)
    return {(c["group"].name, c["estado"], c["fecha"]) for c in fila["chips"]}


# =============================================================================
# C360 · en clase y próximo, con su horizonte
# =============================================================================


def test_en_clase_proximo_y_horizonte(db, profesor, libro):
    """C360. Pasada, futura, demasiado vieja, y lo que sigue del libro."""
    _libro, capitulos = libro
    cap1, (a1, a2, a3) = capitulos[0]
    cap2, (b1, b2) = capitulos[1]
    grupo = _grupo("1º A", profesor)
    GroupBook.objects.create(group=grupo, libro=_libro, seccion="teoria")

    _sesion(grupo, profesor, -3, [a1], cap1, visto=True)
    _sesion(grupo, profesor, -1, [a2], cap1)
    _sesion(grupo, profesor, 2, [a3], cap1)
    _sesion(grupo, profesor, -(lectura.DIAS_ATRAS + 9), [b2], cap2)

    datos = lectura.lista_de_lectura(profesor, hoy=HOY)

    assert _chips(datos, "a1") == {("1º A", lectura.VISTO, HOY - timedelta(days=3))}
    assert _chips(datos, "a2") == {("1º A", lectura.EN_CLASE, HOY - timedelta(days=1))}
    assert _chips(datos, "a3") == {("1º A", lectura.PROXIMO, HOY + timedelta(days=2))}
    # El libro propone sus pendientes, saltándose lo que ya está en una clase:
    # a1, a2 y a3 están en sesiones, así que los tres siguientes son b1 y b2.
    assert _chips(datos, "b1") == {("1º A", lectura.PROXIMO, None)}
    # b2 está en una sesión de hace un mes, fuera del horizonte: como clase no
    # cuenta, pero sigue pendiente en el libro.
    assert _chips(datos, "b2") == {("1º A", lectura.PROXIMO, None)}
    # En clase primero, lo más reciente arriba; luego lo próximo.
    assert _titulos(datos) == ["a2", "a1", "a3", "b1", "b2"]


def test_proximos_por_libro_se_corta(db, profesor):
    """C360. Solo los N siguientes de cada libro, no el libro entero."""
    _libro, _ = _libro_con_capitulos(
        "Largo", "largo-lectura", [("Cap", [f"x{n}" for n in range(8)])]
    )
    grupo = _grupo("1º B", profesor)
    GroupBook.objects.create(group=grupo, libro=_libro, seccion="teoria")

    datos = lectura.lista_de_lectura(profesor, hoy=HOY)

    assert _titulos(datos) == [f"x{n}" for n in range(lectura.PROXIMOS_POR_LIBRO)]


def test_solo_tus_grupos_no_archivados(db, profesor, otro_profesor, libro):
    """C360. Ni grupos ajenos ni archivados."""
    _libro, capitulos = libro
    cap1, (a1, a2, a3) = capitulos[0]
    ajeno = _grupo("Ajeno", otro_profesor)
    archivado = _grupo("Archivado", profesor)
    archivado.archivado = True
    archivado.save()
    _sesion(ajeno, otro_profesor, -1, [a1], cap1)
    _sesion(archivado, profesor, -1, [a2], cap1)

    datos = lectura.lista_de_lectura(profesor, hoy=HOY)

    assert datos["elementos"] == []
    assert [g["group"].name for g in datos["grupos"]] == []


# =============================================================================
# C361 · una fila por elemento, un chip por grupo
# =============================================================================


def test_una_fila_y_un_chip_por_grupo(db, profesor, libro):
    """C361. La misma imagen en dos grupos y dos veces en uno."""
    _libro, capitulos = libro
    cap1, (a1, _a2, _a3) = capitulos[0]
    uno = _grupo("1º A", profesor)
    tres = _grupo("3º C", profesor)
    _sesion(uno, profesor, -5, [a1], cap1)
    _sesion(uno, profesor, -2, [a1], cap1)
    _sesion(tres, profesor, 1, [a1], cap1)

    datos = lectura.lista_de_lectura(profesor, hoy=HOY)

    assert _titulos(datos) == ["a1"]
    assert _chips(datos, "a1") == {
        ("1º A", lectura.EN_CLASE, HOY - timedelta(days=2)),
        ("3º C", lectura.PROXIMO, HOY + timedelta(days=1)),
    }


# =============================================================================
# C362 · artículos y elementos
# =============================================================================


def test_articulos_una_vez_con_los_chips_de_sus_elementos(db, profesor, libro):
    """C362."""
    _libro, capitulos = libro
    cap1, (a1, a2, _a3) = capitulos[0]
    uno = _grupo("1º A", profesor)
    tres = _grupo("3º C", profesor)
    _sesion(uno, profesor, -1, [a1, a2], cap1)
    _sesion(tres, profesor, 3, [a2], cap1)

    datos = lectura.lista_de_lectura(profesor, hoy=HOY)

    assert [a["pagina"].pk for a in datos["articulos"]] == [cap1.pk]
    articulo = datos["articulos"][0]
    assert articulo["elementos"] == 2
    assert {(c["group"].name, c["estado"]) for c in articulo["chips"]} == {
        ("1º A", lectura.EN_CLASE),
        ("3º C", lectura.PROXIMO),
    }
    fila = datos["elementos"][0]
    assert (fila["icono"], fila["tipo_legible"]) == ("🖼️", "Imagen")


# =============================================================================
# C363 · Anti-B · ocultar libros
# =============================================================================


def test_ocultar_un_libro_y_volver_a_mostrarlo(db, profesor, otro_profesor, libro):
    """C363 y Anti-B."""
    _libro, capitulos = libro
    cap1, (a1, a2, _a3) = capitulos[0]
    uno = _grupo("1º A", profesor, otro_profesor)
    tres = _grupo("3º C", profesor)
    gb_uno = GroupBook.objects.create(group=uno, libro=_libro, seccion="ritmo_melodia")
    GroupBook.objects.create(group=tres, libro=_libro, seccion="ritmo_melodia")
    sesion = _sesion(uno, profesor, -1, [a1], cap1)
    sesion.items.update(group_book=gb_uno)
    # El caso de producción: material del libro en una clase SIN libro
    # asociado. Ocultar el libro también lo oculta.
    _sesion(uno, profesor, -1, [a2], cap1)
    # Un extra suelto que no es de ningún libro oculto: sigue saliendo.
    _otro, otros = _libro_con_capitulos("Otro", "otro-lectura", [("Suelto", ["s1"])])
    cap_otro, (s1,) = otros[0]
    _sesion(uno, profesor, -1, [s1], cap_otro)

    assert lectura.alternar_oculto(profesor, _libro) is True
    datos = lectura.lista_de_lectura(profesor, hoy=HOY)
    assert _titulos(datos) == ["s1"]
    assert [l["oculto"] for l in datos["libros"]] == [True]
    assert datos["libros"][0]["grupos"] == ["1º A", "3º C"]

    # Anti-B: al otro profesor del grupo no le cambia nada, ni al grupo.
    assert "a1" in _titulos(lectura.lista_de_lectura(otro_profesor, hoy=HOY))
    assert GroupBook.objects.filter(libro=_libro, activo=True).count() == 2

    assert lectura.alternar_oculto(profesor, _libro) is False
    assert "a1" in _titulos(lectura.lista_de_lectura(profesor, hoy=HOY))


def test_ocultar_por_la_vista(client, profesor, libro):
    """C363, por HTTP: el POST alterna y vuelve a donde estabas."""
    _libro, _ = libro
    _grupo("1º A", profesor)
    client.force_login(profesor)
    url = reverse("clases:lectura_alternar_libro", args=[_libro.pk])

    r = client.post(url, {"next": "/clases/lectura/?cuando=proximo"})
    assert r.status_code == 302 and r["Location"] == "/clases/lectura/?cuando=proximo"
    assert LibroOcultoEnLectura.objects.filter(user=profesor, libro=_libro).exists()

    r = client.post(url, {"next": "https://otro.example.com/"})
    assert r["Location"] == reverse("clases:lectura")
    assert not LibroOcultoEnLectura.objects.exists()


# =============================================================================
# C364 · filtros
# =============================================================================


def test_filtros_de_grupo_y_cuando(db, profesor, otro_profesor, libro):
    """C364. Un pk ajeno se ignora, como en «empezar»."""
    _libro, capitulos = libro
    cap1, (a1, a2, _a3) = capitulos[0]
    uno = _grupo("1º A", profesor)
    tres = _grupo("3º C", profesor)
    ajeno = _grupo("Ajeno", otro_profesor)
    _sesion(uno, profesor, -1, [a1], cap1)
    _sesion(tres, profesor, 2, [a2], cap1)

    assert _titulos(lectura.lista_de_lectura(profesor, [uno.pk], hoy=HOY)) == ["a1"]
    assert _titulos(lectura.lista_de_lectura(profesor, [ajeno.pk], hoy=HOY)) == ["a1", "a2"]
    assert _titulos(lectura.lista_de_lectura(profesor, cuando=lectura.PROXIMO, hoy=HOY)) == ["a2"]
    assert _titulos(lectura.lista_de_lectura(profesor, cuando=lectura.EN_CLASE, hoy=HOY)) == ["a1"]


# =============================================================================
# C365 · Anti-A · Anti-D · la pantalla
# =============================================================================


def test_la_pantalla_enlaza_al_visor_y_no_escribe_nada(client, profesor, libro):
    """C365, Anti-A y Anti-D."""
    _libro, capitulos = libro
    cap1, (a1, _a2, _a3) = capitulos[0]
    uno = _grupo("1º A", profesor)
    GroupBook.objects.create(group=uno, libro=_libro, seccion="teoria")
    _sesion(uno, profesor, -1, [a1], cap1)
    client.force_login(profesor)

    def recuento():
        return [
            m.objects.count()
            for m in (GroupBookItem, ClassSessionItem, ClassSession, LibraryItem)
        ]

    antes = recuento()
    r = client.get(reverse("clases:lectura") + f"?grupo={uno.pk}&cuando=")
    html = r.content.decode()
    tipo = ContentType.objects.get_for_model(a1)
    visor = reverse("my_library:view_content_object", args=[tipo.pk, a1.pk])

    assert r.status_code == 200
    assert f'href="{visor}?back=' in html
    assert f'href="{cap1.url}"' in html
    assert "1º A · en clase" in html
    assert "{#" not in html

    assert client.get(visor + "?back=/clases/lectura/").status_code == 200
    assert recuento() == antes


def test_el_alumnado_no_entra(client, django_user_model):
    alumno = django_user_model.objects.create_user(email="alu@example.com", password="x")
    client.force_login(alumno)
    assert client.get(reverse("clases:lectura")).status_code == 302


# =============================================================================
# C366 · un libro en varios grupos se recorre una vez
# =============================================================================


def test_un_libro_en_varios_grupos_se_recorre_una_vez(db, profesor, libro):
    """C366."""
    _libro, _ = libro
    for nombre in ("1º A", "1º B", "1º C"):
        GroupBook.objects.create(group=_grupo(nombre, profesor), libro=_libro, seccion="teoria")

    with mock.patch(
        "clases.lectura.material_del_libro", wraps=lectura.material_del_libro
    ) as recorrido:
        datos = lectura.lista_de_lectura(profesor, hoy=HOY)

    assert recorrido.call_count == 1
    assert len(_chips(datos, "a1")) == 3
