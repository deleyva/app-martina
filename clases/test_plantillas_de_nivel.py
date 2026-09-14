"""Fase 32 — Plantillas de nivel. Una plantilla es un grupo sin alumnos.

Montar «lo que se da en tercero» una vez y mandarlo a los grupos que elijas, en
vez de repetir la misma faena en cada uno. La plantilla no desaparece al enviar:
se queda, y por eso un libro nuevo en marzo se configura una vez y se envía.

**Por qué una plantilla es un `Group`.** Así el motor entero funciona sin tocar
nada. El precio es que podría colarse en cualquier pantalla que liste grupos, y
ese precio se paga en el gestor por defecto, no pantalla por pantalla.
"""

import pytest

from clases.models import Group, Subject


def _asignatura():
    return Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})[0]


def _plantilla(profesor, nombre="3.º ESO"):
    plantilla = Group.todos.create(
        name=nombre,
        subject=_asignatura(),
        academic_year="2026-2027",
        es_plantilla=True,
    )
    plantilla.teachers.add(profesor)
    return plantilla


def _clase(profesor, nombre="3-C-BIL"):
    grupo = Group.objects.create(
        name=nombre, subject=_asignatura(), academic_year="2026-2027"
    )
    grupo.teachers.add(profesor)
    return grupo


@pytest.fixture
def profe(db, django_user_model):
    return django_user_model.objects.create_user(email="plantillas@x.es", password="x")


# =============================================================================
# C176 · La plantilla no se cuela por ningún lado
# =============================================================================


def test_la_relacion_inversa_no_trae_plantillas(profe):
    """**El cimiento de todo el diseño, y por eso tiene test propio.**

    Hay nueve sitios en el código que preguntan `user.teaching_groups` fuera del
    embudo de `del_profesor`: la navegación, las evaluaciones, la programación,
    las fichas de estudio. Ninguno se ha tocado. Lo que los protege es que
    Django construye el gestor inverso a partir del gestor por defecto, así que
    el filtro de `GrupoManager` llega solo hasta ahí.

    Si una versión de Django cambiara eso, este test cae y avisa antes de que
    una plantilla aparezca en el menú de alguien.
    """
    clase = _clase(profe)
    plantilla = _plantilla(profe)

    desde_la_relacion = set(profe.teaching_groups.all())

    assert desde_la_relacion == {clase}, "la plantilla se ha colado por la relación inversa"
    assert plantilla in set(Group.todos.filter(teachers=profe))


def test_el_gestor_por_defecto_no_ve_plantillas(profe):
    _clase(profe)
    plantilla = _plantilla(profe)

    assert plantilla not in Group.objects.all()
    assert plantilla in Group.todos.all()


def test_una_relacion_hacia_dentro_si_resuelve_la_plantilla(profe):
    """`base_manager_name`. Sin esto, un `GroupBook` de una plantilla no podría
    leer su propio grupo y el motor reventaría en la primera pantalla."""
    from my_library.tests import _libro_con_capitulos
    from clases.models import GroupBook

    plantilla = _plantilla(profe)
    libro, _ = _libro_con_capitulos("Teoría", "teoria-plantilla", [("Cap", ["m1"])])
    group_book = GroupBook.objects.create(
        group=plantilla, libro=libro, seccion="teoria"
    )

    de_vuelta = GroupBook.objects.get(pk=group_book.pk)

    assert de_vuelta.group == plantilla, "el motor no puede leer el grupo de la plantilla"


def test_del_profesor_no_trae_plantillas(profe):
    clase = _clase(profe)
    plantilla = _plantilla(profe)

    assert list(Group.del_profesor(profe)) == [clase]
    assert plantilla not in Group.del_profesor(profe, incluir_archivados=True)


# =============================================================================
# C176 · Por HTTP: la plantilla no sale en ninguna pantalla de clases
# =============================================================================
#
# El test va por las pantallas y no por el ORM a propósito. El agujero de
# `archivado` se coló justamente así: el filtro estaba puesto en el sitio
# evidente y faltaba en una pantalla que nadie volvió a mirar.


@pytest.mark.parametrize(
    "ruta",
    [
        "clases:class_session_list",
        "clases:class_session_create",
        "clases:progreso",
    ],
)
def test_la_plantilla_no_sale_en_las_pantallas_de_clase(client, profe, ruta):
    from django.urls import reverse

    _clase(profe, "3-C-BIL")
    _plantilla(profe, "3.º ESO")
    client.force_login(profe)

    respuesta = client.get(reverse(ruta))
    cuerpo = respuesta.content.decode()

    assert respuesta.status_code == 200
    assert "3-C-BIL" in cuerpo, "la clase de verdad tiene que salir"
    assert "3.º ESO" not in cuerpo, f"la plantilla se ha colado en {ruta}"


def test_la_plantilla_sale_en_su_propia_pantalla(client, profe):
    from django.urls import reverse

    _clase(profe, "3-C-BIL")
    _plantilla(profe, "3.º ESO")
    client.force_login(profe)

    cuerpo = client.get(reverse("clases:niveles")).content.decode()

    assert "3.º ESO" in cuerpo
    assert "3-C-BIL" not in cuerpo, "las clases no son plantillas"


# =============================================================================
# C177 · Ni alumnado ni sesiones dentro de una plantilla
# =============================================================================


def test_no_se_invita_alumnado_a_una_plantilla(client, profe):
    from django.urls import reverse

    plantilla = _plantilla(profe)
    client.force_login(profe)

    respuesta = client.get(
        reverse("clases:group_invitations", args=[plantilla.pk])
    )

    assert respuesta.status_code == 404


def test_no_se_crea_una_sesion_en_una_plantilla(client, profe):
    """Por POST, no mirando el desplegable: el desplegable se puede saltar
    escribiendo el `group` a mano, y eso es lo que hay que cerrar."""
    from datetime import date
    from django.urls import reverse

    from clases.models import ClassSession

    plantilla = _plantilla(profe)
    client.force_login(profe)

    client.post(
        reverse("clases:class_session_create"),
        {"group": plantilla.pk, "date": date.today().isoformat(), "title": "Colada"},
    )

    assert not ClassSession.objects.filter(group=plantilla).exists()


# =============================================================================
# C183 · Una plantilla es de quien la hizo
# =============================================================================


@pytest.mark.parametrize(
    "ruta", ["clases:group_books_index", "clases:group_book_add"]
)
def test_otro_profesor_no_llega_a_tu_plantilla(client, profe, django_user_model, ruta):
    from django.urls import reverse

    plantilla = _plantilla(profe)
    intruso = django_user_model.objects.create_user(email="otro@x.es", password="x")
    _clase(intruso, "1-G-BIL")
    client.force_login(intruso)

    url = reverse(ruta, args=[plantilla.pk])
    respuesta = client.post(url) if "add" in ruta else client.get(url)

    assert respuesta.status_code == 404


def test_las_plantillas_de_otro_no_salen_en_tu_lista(client, profe, django_user_model):
    """El nombre es raro a propósito: con «3.º ESO» este test pasaba por accidente
    al principio y fallaba por otro motivo —el formulario lo trae de ejemplo en
    su `placeholder`—. Un nombre que solo puede venir de la base de datos es lo
    que hace que el test mida lo que dice medir."""
    from django.urls import reverse

    _plantilla(profe, "Nivel de otro profesor")
    otro = django_user_model.objects.create_user(email="otro2@x.es", password="x")
    _clase(otro, "1-G-BIL")
    client.force_login(otro)

    cuerpo = client.get(reverse("clases:niveles")).content.decode()

    assert "Nivel de otro profesor" not in cuerpo
