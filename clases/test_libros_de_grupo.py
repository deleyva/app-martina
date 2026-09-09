"""Fase 28 — Libros que dan clase. Los falsadores de C124 a C129.

Las afirmaciones que importan son universales, no de ejemplo: C125 se comprueba
contando TODAS las filas de `GroupBookItem` y no mirando una, y C126 se
comprueba con dos grupos sobre el mismo libro, que es el único montaje capaz de
refutarla.

Los ayudantes de construcción de libros son los de `my_library.tests`, a
propósito: si el motor de grupos se probara contra libros de mentira, pasaría
los tests y fallaría con los libros reales.
"""

import pytest

from clases import libros_de_grupo
from clases.models import (
    ClassSession,
    ClassSessionItem,
    Group,
    GroupBook,
    GroupBookItem,
    Subject,
)
from my_library.tests import _libro_con_capitulos, _libro_por_referencia


# =============================================================================
# Montaje
# =============================================================================


def _grupo(nombre="1º ESO A"):
    asignatura, _ = Subject.objects.get_or_create(
        name="Música", defaults={"code": "MUS"}
    )
    return Group.objects.create(
        name=nombre, subject=asignatura, academic_year="2026-2027"
    )


def _asignar(grupo, libro, seccion="teoria", modo=GroupBook.SECUENCIAL):
    return GroupBook.objects.create(
        group=grupo, libro=libro, seccion=seccion, modo=modo
    )


def _sesion(grupo, profesor):
    from django.utils import timezone

    return ClassSession.objects.create(
        teacher=profesor,
        group=grupo,
        date=timezone.now().date(),
        title="Clase de prueba",
    )


@pytest.fixture
def profesor(django_user_model):
    return django_user_model.objects.create_user(
        email="profe@example.com", password="x", is_staff=True
    )


# =============================================================================
# C124 · Los dos tipos de libro valen
# =============================================================================


def test_libro_por_arbol_se_enumera(db):
    """C124. Un `LibroPage` con páginas hijas."""
    libro, _ = _libro_con_capitulos(
        "Método por árbol", "metodo-arbol", [("Capítulo 1", ["a1", "a2"])]
    )
    group_book = _asignar(_grupo(), libro)

    filas = libros_de_grupo.enumerar(group_book)

    assert [f["titulo"] for f in filas] == ["a1", "a2"]


def test_libro_por_referencia_se_enumera(db):
    """C124. Un `LibroDeEstudioPage` que apunta a páginas de otro sitio del árbol.

    Es el tipo que hace falta para las canciones: en Wagtail una página tiene un
    solo padre, así que agrupar por el árbol obligaría a que cada canción
    viviera en un único libro para siempre.
    """
    _indice, capitulos = _libro_con_capitulos(
        "Sueltas", "sueltas-ref", [("Hotel California", ["hc1", "hc2"])]
    )
    pagina = capitulos[0][0]
    libro = _libro_por_referencia("Canciones de 3º", "canciones-3", [pagina])
    group_book = _asignar(_grupo(), libro, seccion="cancion")

    filas = libros_de_grupo.enumerar(group_book)

    assert [f["titulo"] for f in filas] == ["hc1", "hc2"]


# =============================================================================
# C125 · Fila de excepción, no copia
# =============================================================================


def test_asignar_y_enumerar_no_crea_ni_una_fila(db):
    """C125. El invariante entero del diseño, y se comprueba contando TODAS.

    Si esto falla, el sistema ha vuelto a copiar el material por adelantado, que
    es exactamente lo que hace inviable un libro de 283 medios por cada grupo.
    """
    libro, _ = _libro_con_capitulos(
        "Grande", "grande", [("Cap 1", ["m1", "m2", "m3"]), ("Cap 2", ["m4", "m5"])]
    )
    group_book = _asignar(_grupo(), libro)

    filas = libros_de_grupo.enumerar(group_book)

    assert len(filas) == 5
    assert GroupBookItem.objects.count() == 0


def test_solo_nace_fila_al_tocar_algo(db):
    """C125. Y nace UNA, no una por elemento del libro."""
    libro, _ = _libro_con_capitulos("Libro", "libro-toque", [("Cap", ["m1", "m2", "m3"])])
    group_book = _asignar(_grupo(), libro)

    fila = libros_de_grupo.enumerar(group_book)[1]
    libros_de_grupo.excepcion(group_book, fila["objeto"], incluido=False)

    assert GroupBookItem.objects.count() == 1
    assert GroupBookItem.objects.get().incluido is False


# =============================================================================
# C126 · Lo que toca un grupo no toca a otro
# =============================================================================


def test_dos_grupos_sobre_el_mismo_libro_no_se_pisan(db):
    """C126. El único montaje capaz de refutar la afirmación.

    Un solo grupo pasaría el test aunque el estado estuviera guardado en el
    libro y fuera global, que es justo el fallo que se quiere descartar.
    """
    libro, _ = _libro_con_capitulos("Compartido", "compartido", [("Cap", ["m1", "m2"])])
    grupo_a, grupo_b = _grupo("1º ESO A"), _grupo("1º ESO B")
    gb_a, gb_b = _asignar(grupo_a, libro), _asignar(grupo_b, libro)

    # A excluye el primero.
    primero = libros_de_grupo.enumerar(gb_a)[0]
    libros_de_grupo.excepcion(gb_a, primero["objeto"], incluido=False)

    siguiente_a = libros_de_grupo.siguientes(gb_a)[0]
    siguiente_b = libros_de_grupo.siguientes(gb_b)[0]

    assert siguiente_a["titulo"] == "m2"
    assert siguiente_b["titulo"] == "m1"


def test_recolocar_solo_afecta_a_su_grupo(db):
    """C126. El orden también es del grupo, no del libro."""
    libro, _ = _libro_con_capitulos("Orden", "orden", [("Cap", ["m1", "m2", "m3"])])
    grupo_a, grupo_b = _grupo("2º ESO A"), _grupo("2º ESO B")
    gb_a, gb_b = _asignar(grupo_a, libro), _asignar(grupo_b, libro)

    claves = [(f["tipo"].pk, f["objeto"].pk) for f in libros_de_grupo.enumerar(gb_a)]
    claves.reverse()
    libros_de_grupo.recolocar(gb_a, claves)

    assert [f["titulo"] for f in libros_de_grupo.enumerar(gb_a)] == ["m3", "m2", "m1"]
    assert [f["titulo"] for f in libros_de_grupo.enumerar(gb_b)] == ["m1", "m2", "m3"]


# =============================================================================
# C127 · Preparar la sesión, en el orden de la clase
# =============================================================================


def test_preparar_respeta_el_orden_de_la_clase(db, profesor):
    """C127. El orden sale de la sección, no del orden en que se asignaron.

    Se asignan a propósito al revés del orden de la clase: si el sistema
    ordenara por fecha de asignación o alfabéticamente, este test lo caza.
    """
    grupo = _grupo()
    grupo.teachers.add(profesor)

    canciones, _ = _libro_con_capitulos("Canciones", "canciones", [("C", ["cancion1"])])
    teoria, _ = _libro_con_capitulos("Teoría", "teoria", [("T", ["teoria1"])])
    ritmo, _ = _libro_con_capitulos("Ritmo", "ritmo", [("R", ["ritmo1"])])

    _asignar(grupo, canciones, seccion="cancion", modo=GroupBook.EN_CURSO)
    _asignar(grupo, ritmo, seccion="ritmo_melodia")
    _asignar(grupo, teoria, seccion="teoria")

    sesion = _sesion(grupo, profesor)
    creados = libros_de_grupo.preparar_sesion(sesion)

    assert [i.seccion for i in creados] == ["teoria", "ritmo_melodia", "cancion"]
    assert [i.order for i in creados] == [0, 1, 2]


def test_preparar_dos_veces_avanza_pero_nunca_repite(db, profesor):
    """C127. El invariante es que un elemento no entre dos veces en la clase.

    La segunda pulsación NO es una no-operación: ofrece el siguiente. Se decidió
    así al arreglar la vista previa, que antes enseñaba lo que ya estaba en la
    sesión y luego el botón no lo añadía —o sea, prometía un trabajo que no
    hacía. Ahora la previa descuenta lo puesto, y lo que enseña es lo que entra.
    """
    grupo = _grupo()
    grupo.teachers.add(profesor)
    libro, _ = _libro_con_capitulos("Libro", "libro-dup", [("Cap", ["m1", "m2"])])
    _asignar(grupo, libro)

    sesion = _sesion(grupo, profesor)
    primeros = libros_de_grupo.preparar_sesion(sesion)
    segundos = libros_de_grupo.preparar_sesion(sesion)

    assert [i.content_object.title for i in primeros] == ["m1"]
    assert [i.content_object.title for i in segundos] == ["m2"]

    # El invariante de verdad: ni un elemento repetido en la sesión.
    claves = [(i.content_type_id, i.object_id) for i in sesion.items.all()]
    assert len(claves) == len(set(claves)) == 2


def test_preparar_no_ofrece_lo_que_ya_esta_en_la_clase(db, profesor):
    """C127. Con el libro agotado, la tercera pulsación ya no añade nada."""
    grupo = _grupo()
    grupo.teachers.add(profesor)
    libro, _ = _libro_con_capitulos("Libro", "libro-fin", [("Cap", ["m1"])])
    _asignar(grupo, libro)

    sesion = _sesion(grupo, profesor)
    libros_de_grupo.preparar_sesion(sesion)

    assert libros_de_grupo.preparar_sesion(sesion) == []
    assert sesion.items.count() == 1


def test_la_vista_previa_dice_lo_mismo_que_la_preparacion(db, profesor):
    """C127. Si divergen, la vista previa miente y deja de servir para nada."""
    grupo = _grupo()
    grupo.teachers.add(profesor)
    libro, _ = _libro_con_capitulos("Libro", "libro-prev", [("Cap", ["m1", "m2"])])
    _asignar(grupo, libro)

    previa = libros_de_grupo.previsualizar_sesion(grupo)
    creados = libros_de_grupo.preparar_sesion(_sesion(grupo, profesor))

    assert [f["objeto"].pk for f in previa] == [i.object_id for i in creados]


def test_un_libro_inactivo_no_propone(db, profesor):
    """C127. Desactivar es cómo se para un libro sin perder su avance."""
    grupo = _grupo()
    grupo.teachers.add(profesor)
    libro, _ = _libro_con_capitulos("Libro", "libro-off", [("Cap", ["m1"])])
    group_book = _asignar(grupo, libro)
    group_book.activo = False
    group_book.save()

    assert libros_de_grupo.preparar_sesion(_sesion(grupo, profesor)) == []


# =============================================================================
# C128 · El modo «en curso» no se agota al marcar visto
# =============================================================================


def test_en_curso_sigue_proponiendo_despues_de_marcar_visto(db, profesor):
    """C128. La razón de que existan dos modos.

    Una canción se trabaja durante semanas: si marcar un elemento visto la
    sacara de la clase, o desaparecería en la segunda sesión o se dejaría de
    marcar nada por miedo, y entonces el motor no avanza.
    """
    grupo = _grupo()
    grupo.teachers.add(profesor)
    libro, _ = _libro_con_capitulos(
        "Canción", "cancion-larga", [("Estrofa", ["parte1", "parte2", "parte3"])]
    )
    _asignar(grupo, libro, seccion="cancion", modo=GroupBook.EN_CURSO)

    primera = _sesion(grupo, profesor)
    item = libros_de_grupo.preparar_sesion(primera)[0]
    libros_de_grupo.marcar_visto(item)

    segunda = libros_de_grupo.preparar_sesion(_sesion(grupo, profesor))

    assert len(segunda) == 1
    assert segunda[0].content_object.title == "parte2"


def test_marcar_visto_es_reversible(db, profesor):
    """C128. En clase se dan toques por error; sin vuelta atrás se deja de marcar."""
    grupo = _grupo()
    grupo.teachers.add(profesor)
    libro, _ = _libro_con_capitulos("Libro", "libro-undo", [("Cap", ["m1", "m2"])])
    group_book = _asignar(grupo, libro)

    item = libros_de_grupo.preparar_sesion(_sesion(grupo, profesor))[0]
    libros_de_grupo.marcar_visto(item)
    assert libros_de_grupo.siguientes(group_book)[0]["titulo"] == "m2"

    libros_de_grupo.marcar_visto(item, visto=False)
    assert libros_de_grupo.siguientes(group_book)[0]["titulo"] == "m1"


# =============================================================================
# C129 · Los extras no ensucian los libros
# =============================================================================


def test_un_extra_no_mueve_la_progresion(db, profesor):
    """C129. «Poder añadir algún ítem extra a una clase sin ensuciar los libros»."""
    grupo = _grupo()
    grupo.teachers.add(profesor)
    libro, _ = _libro_con_capitulos("Libro", "libro-extra", [("Cap", ["m1", "m2"])])
    group_book = _asignar(grupo, libro)

    otro, capitulos = _libro_con_capitulos("Suelto", "suelto", [("Cap", ["extra1"])])
    imagen = capitulos[0][1][0]

    sesion = _sesion(grupo, profesor)
    from django.contrib.contenttypes.models import ContentType

    extra = ClassSessionItem.objects.create(
        session=sesion,
        content_type=ContentType.objects.get_for_model(imagen),
        object_id=imagen.pk,
        order=0,
    )
    libros_de_grupo.marcar_visto(extra)

    assert extra.group_book_id is None
    assert GroupBookItem.objects.count() == 0
    assert libros_de_grupo.siguientes(group_book)[0]["titulo"] == "m1"


# =============================================================================
# C137-C140 · El bañado a las bibliotecas del alumnado
# =============================================================================


def _matricular(grupo, django_user_model, cuantos=2):
    from clases.models import Enrollment

    alumnos = []
    for n in range(cuantos):
        alumno = django_user_model.objects.create_user(
            email=f"alumno{n}-{grupo.pk}@example.com", password="x"
        )
        Enrollment.objects.create(user=alumno, group=grupo, is_active=True)
        alumnos.append(alumno)
    return alumnos


def _montar_clase(grupo, profesor, a_casa):
    """Un libro de un elemento, puesto en una sesión, con `a_casa` a lo que se pida."""
    libro, _ = _libro_con_capitulos(
        f"Libro {a_casa}-{grupo.pk}", f"libro-casa-{a_casa}-{grupo.pk}", [("Cap", ["m1"])]
    )
    group_book = _asignar(grupo, libro, seccion="instrumento")
    fila = libros_de_grupo.enumerar(group_book)[0]
    libros_de_grupo.excepcion(
        group_book, fila["objeto"], capitulo=fila["capitulo"], a_casa=a_casa
    )
    sesion = _sesion(grupo, profesor)
    return group_book, libros_de_grupo.preparar_sesion(sesion)[0]


def test_lo_marcado_para_casa_baja_a_cada_alumno(db, profesor, django_user_model):
    """C137. Dar por visto es el único gesto que manda material a casa."""
    from my_library.models import LibraryItem

    grupo = _grupo()
    grupo.teachers.add(profesor)
    alumnos = _matricular(grupo, django_user_model)
    _, item = _montar_clase(grupo, profesor, a_casa=True)

    libros_de_grupo.marcar_visto(item)

    assert LibraryItem.objects.filter(user__in=alumnos).count() == 2


def test_lo_no_marcado_no_baja(db, profesor, django_user_model):
    """C137. Y es la mitad del argumento: sin esto, la biblioteca del alumnado se
    llena de dictados y ejercicios sensoriales de un solo uso."""
    from my_library.models import LibraryItem

    grupo = _grupo()
    grupo.teachers.add(profesor)
    alumnos = _matricular(grupo, django_user_model)
    _, item = _montar_clase(grupo, profesor, a_casa=False)

    libros_de_grupo.marcar_visto(item)

    assert LibraryItem.objects.filter(user__in=alumnos).count() == 0


def test_marcar_visto_dos_veces_no_duplica_en_la_biblioteca(db, profesor, django_user_model):
    """C138. La unicidad es (usuario, tipo, objeto), y aquí se comprueba que de
    verdad no duplica y no solo que no revienta: un elemento repetido saldría dos
    veces en la cola de estudio del alumno."""
    from my_library.models import LibraryItem

    grupo = _grupo()
    grupo.teachers.add(profesor)
    alumnos = _matricular(grupo, django_user_model)
    _, item = _montar_clase(grupo, profesor, a_casa=True)

    libros_de_grupo.marcar_visto(item)
    libros_de_grupo.bajar_a_las_bibliotecas(
        item, GroupBookItem.objects.get(a_casa=True)
    )

    assert LibraryItem.objects.filter(user__in=alumnos).count() == 2


def test_deshacer_retira_lo_intacto(db, profesor, django_user_model):
    """C139. Un toque mal dado mete el elemento en treinta bibliotecas; deshacer
    justo después tiene que limpiarlo."""
    from my_library.models import LibraryItem

    grupo = _grupo()
    grupo.teachers.add(profesor)
    alumnos = _matricular(grupo, django_user_model)
    _, item = _montar_clase(grupo, profesor, a_casa=True)

    libros_de_grupo.marcar_visto(item)
    libros_de_grupo.marcar_visto(item, visto=False)

    assert LibraryItem.objects.filter(user__in=alumnos).count() == 0


def test_deshacer_respeta_lo_que_el_alumno_ya_practico(db, profesor, django_user_model):
    """C140. El límite del deshacer, y no es un detalle: `ReviewLog` cuelga del
    `LibraryItem` en cascada, así que llevarse uno ya practicado destruiría el
    historial de ese alumno. Se borra lo intacto y se respeta lo demás."""
    from my_library.models import LibraryItem, ReviewLog

    grupo = _grupo()
    grupo.teachers.add(profesor)
    alumnos = _matricular(grupo, django_user_model)
    _, item = _montar_clase(grupo, profesor, a_casa=True)

    libros_de_grupo.marcar_visto(item)

    # Un alumno lo practica; el otro no lo ha abierto.
    practicado = LibraryItem.objects.get(user=alumnos[0])
    ReviewLog.objects.create(user=alumnos[0], item=practicado)

    libros_de_grupo.marcar_visto(item, visto=False)

    assert LibraryItem.objects.filter(user=alumnos[0]).count() == 1
    assert LibraryItem.objects.filter(user=alumnos[1]).count() == 0
    assert ReviewLog.objects.filter(item=practicado).exists()


def test_un_extra_suelto_nunca_baja(db, profesor, django_user_model):
    """C141. Sin libro no hay `a_casa`, así que un extra añadido a mano se ve en
    clase y no llega a ninguna biblioteca."""
    from django.contrib.contenttypes.models import ContentType
    from my_library.models import LibraryItem

    grupo = _grupo()
    grupo.teachers.add(profesor)
    alumnos = _matricular(grupo, django_user_model)
    _otro, capitulos = _libro_con_capitulos("Suelto", "suelto-casa", [("Cap", ["extra1"])])
    imagen = capitulos[0][1][0]

    sesion = _sesion(grupo, profesor)
    extra = ClassSessionItem.objects.create(
        session=sesion,
        content_type=ContentType.objects.get_for_model(imagen),
        object_id=imagen.pk,
        order=0,
    )
    libros_de_grupo.marcar_visto(extra)

    assert LibraryItem.objects.filter(user__in=alumnos).count() == 0


# =============================================================================
# C142 · El panel de avance
# =============================================================================


def test_el_panel_dice_que_toca_en_cada_grupo(db, profesor):
    """C142. La pregunta al preparar una clase no es cuánto llevas sino qué toca."""
    grupo = _grupo()
    grupo.teachers.add(profesor)
    libro, _ = _libro_con_capitulos("Método", "metodo-panel", [("Cap", ["m1", "m2"])])
    group_book = _asignar(grupo, libro, seccion="ritmo_melodia")

    fila = libros_de_grupo.enumerar(group_book)[0]
    libros_de_grupo.excepcion(
        group_book, fila["objeto"], capitulo=fila["capitulo"],
        estado=GroupBookItem.VISTO,
    )

    panel = libros_de_grupo.panel_de_progreso(profesor)

    assert len(panel) == 1
    libros = panel[0]["libros"]
    assert libros[0]["vistos"] == 1
    assert libros[0]["total"] == 2
    assert libros[0]["siguiente"]["titulo"] == "m2"


def test_el_panel_avisa_de_un_libro_terminado(db, profesor):
    """C142. Sin siguiente, el panel tiene que decirlo en vez de callarse."""
    grupo = _grupo()
    grupo.teachers.add(profesor)
    libro, _ = _libro_con_capitulos("Corto", "corto-panel", [("Cap", ["unico"])])
    group_book = _asignar(grupo, libro)

    fila = libros_de_grupo.enumerar(group_book)[0]
    libros_de_grupo.excepcion(
        group_book, fila["objeto"], capitulo=fila["capitulo"],
        estado=GroupBookItem.VISTO,
    )

    panel = libros_de_grupo.panel_de_progreso(profesor)

    assert panel[0]["libros"][0]["siguiente"] is None


# =============================================================================
# C143 · Marcar «a casa» en mitad de la clase
# =============================================================================


def test_marcar_a_casa_con_el_elemento_ya_visto_baja_en_ese_momento(
    db, profesor, django_user_model
):
    """C143. La razón de ser del botón en el visor.

    Sin esto, marcar la casita después de haberlo dado por visto no haría nada
    hasta desmarcar y volver a marcar el visto, que es justo la fricción que el
    botón existe para quitar.
    """
    from my_library.models import LibraryItem

    grupo = _grupo()
    grupo.teachers.add(profesor)
    alumnos = _matricular(grupo, django_user_model)
    _, item = _montar_clase(grupo, profesor, a_casa=False)

    libros_de_grupo.marcar_visto(item)
    assert LibraryItem.objects.filter(user__in=alumnos).count() == 0

    libros_de_grupo.marcar_a_casa(item, True)

    assert LibraryItem.objects.filter(user__in=alumnos).count() == 2


def test_desmarcar_a_casa_con_el_elemento_ya_visto_lo_retira(
    db, profesor, django_user_model
):
    """C143. Y en el otro sentido, que es donde estaba el defecto: al desmarcar,
    `a_casa` ya vale False, así que si la retirada se lo preguntara al modelo no
    retiraría nunca nada."""
    from my_library.models import LibraryItem

    grupo = _grupo()
    grupo.teachers.add(profesor)
    alumnos = _matricular(grupo, django_user_model)
    _, item = _montar_clase(grupo, profesor, a_casa=True)

    libros_de_grupo.marcar_visto(item)
    assert LibraryItem.objects.filter(user__in=alumnos).count() == 2

    libros_de_grupo.marcar_a_casa(item, False)

    assert LibraryItem.objects.filter(user__in=alumnos).count() == 0


def test_marcar_a_casa_sin_verlo_no_baja_nada_todavia(db, profesor, django_user_model):
    """C143. La casita sola no manda nada: lo que manda es darlo por visto."""
    from my_library.models import LibraryItem

    grupo = _grupo()
    grupo.teachers.add(profesor)
    alumnos = _matricular(grupo, django_user_model)
    _, item = _montar_clase(grupo, profesor, a_casa=False)

    libros_de_grupo.marcar_a_casa(item, True)

    assert LibraryItem.objects.filter(user__in=alumnos).count() == 0


def test_un_extra_suelto_no_admite_casita(db, profesor):
    """C143. Sin libro no hay dónde apuntar la decisión, y el visor lo dice en
    vez de fingir que se ha guardado."""
    from django.contrib.contenttypes.models import ContentType

    grupo = _grupo()
    grupo.teachers.add(profesor)
    _otro, capitulos = _libro_con_capitulos("Suelto", "suelto-casita", [("Cap", ["x1"])])
    imagen = capitulos[0][1][0]

    extra = ClassSessionItem.objects.create(
        session=_sesion(grupo, profesor),
        content_type=ContentType.objects.get_for_model(imagen),
        object_id=imagen.pk,
        order=0,
    )

    assert libros_de_grupo.marcar_a_casa(extra, True) is None
    assert GroupBookItem.objects.count() == 0
