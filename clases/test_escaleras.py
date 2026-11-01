"""Fase 93 — Escaleras de peldaños y el guión de la clase. Falsadores de C625 a C631.

La app sabía QUÉ había visto cada grupo, pero no HASTA DÓNDE lo había
trabajado. Aquí se falsan las afirmaciones que importan:

- **Un libro sin escalera no cambia en nada** (Anti-B): tratado no crea fila
  en el libro, igual que en la fase 68.
- **Tratado sube UN peldaño, y «+2» dos**; cualquier otra marca retira lo que
  ese toque puso, y nada más (pedido de Jesús: uno por defecto).
- **Completar la escalera da por visto; quitar un peldaño devuelve a la cola.**
- **Preparar propone el primer elemento no completado con su siguiente peldaño.**
- **El botón «Guión» va entre «Comenzar clase» y «Editar», y el alumnado no lo ve.**
"""

from datetime import date

import pytest
from django.urls import reverse

from clases import escaleras, libros_de_grupo
from clases.models import (
    ClassSession,
    ClassSessionItem,
    Enrollment,
    Escalera,
    GroupBook,
    GroupBookItem,
)
from clases.test_marcas_preparar import _grupo
from my_library.tests import _libro_con_capitulos


@pytest.fixture
def profesor(django_user_model):
    return django_user_model.objects.create_user(email="profe-esc@x.es", password="x")


@pytest.fixture
def de_fabrica(db):
    escaleras.crear_de_fabrica()
    return {e.nombre: e for e in Escalera.objects.all()}


@pytest.fixture
def montaje(db, profesor, de_fabrica):
    """Un libro de canciones con escalera y uno de teoría sin ella, en un grupo."""
    canciones, _ = _libro_con_capitulos(
        "Canciones", "canciones-escalera", [("Bloque 1", ["c1", "c2", "c3"])]
    )
    teoria, _ = _libro_con_capitulos("Teoría", "teoria-escalera", [("Tema 1", ["t1", "t2"])])
    grupo = _grupo(profesor, "3-FH")
    gb = GroupBook.objects.create(
        group=grupo,
        libro=canciones,
        seccion="cancion",
        modo=GroupBook.EN_CURSO,
        escalera=de_fabrica["Canción"],
    )
    gb_teoria = GroupBook.objects.create(group=grupo, libro=teoria, seccion="teoria")
    return {"grupo": grupo, "gb": gb, "gb_teoria": gb_teoria, "cancion": de_fabrica["Canción"]}


def _fila(group_book, titulo):
    for fila in libros_de_grupo.enumerar(group_book):
        if fila["titulo"] == titulo:
            return fila
    raise AssertionError(f"no hay {titulo}")


def _sesion(profesor, grupo):
    return ClassSession.objects.create(
        teacher=profesor, group=grupo, date=date(2026, 11, 2), title="Clase"
    )


def _item_del_grupo(group_book, fila):
    return GroupBookItem.objects.filter(
        group_book=group_book, content_type=fila["tipo"], object_id=fila["objeto"].pk
    ).first()


def _tratar(client, item, valor, saltos=None):
    datos = {"valor": valor}
    if saltos:
        datos["saltos"] = str(saltos)
    return client.post(reverse("clases:class_session_item_tratado", args=[item.pk]), datos)


# =============================================================================
# C625 · Las cuatro de fábrica
# =============================================================================


def test_las_cuatro_de_fabrica_con_sus_peldanos(db):
    """C625. Cuatro escaleras, con 5, 4, 3 y 5 peldaños, y crearlas dos veces no duplica."""
    escaleras.crear_de_fabrica()
    assert escaleras.crear_de_fabrica() == 0
    por_nombre = {e.nombre: e for e in Escalera.objects.all()}
    assert set(por_nombre) >= {
        "Lectura rítmica",
        "Lectura melódica",
        "Ordenamientos (sensorialidad)",
        "Canción",
    }
    assert por_nombre["Lectura rítmica"].total == 5
    assert por_nombre["Lectura melódica"].claves == ["ritmo", "na", "notas", "notas_canto"]
    assert por_nombre["Ordenamientos (sensorialidad)"].claves == ["na", "notas", "notas_canto"]
    assert por_nombre["Canción"].total == 5
    assert por_nombre["Canción"].nombre_de("armonia") == "Progresión armónica"
    assert por_nombre["Canción"].indice("armonia") == 3


def test_el_admin_lista_las_escaleras(client, de_fabrica, django_user_model):
    admin = django_user_model.objects.create_superuser(email="admin-esc@x.es", password="x")
    client.force_login(admin)
    r = client.get("/admin/clases/escalera/")
    assert r.status_code == 200
    assert "Lectura melódica" in r.content.decode()


# =============================================================================
# C626 · La escalera va por libro del grupo
# =============================================================================


def test_un_libro_de_canciones_nace_con_escalera_y_el_resto_sin(client, profesor, de_fabrica):
    """C626."""
    grupo = _grupo(profesor, "1-A")
    canciones, _ = _libro_con_capitulos("Más canciones", "mas-canciones", [("B", ["x1"])])
    ritmo, _ = _libro_con_capitulos("Ritmos", "ritmos-esc", [("R", ["r1"])])
    client.force_login(profesor)

    client.post(
        reverse("clases:group_book_add", args=[grupo.pk]),
        {"libro": canciones.pk, "seccion": "cancion"},
    )
    client.post(
        reverse("clases:group_book_add", args=[grupo.pk]),
        {"libro": ritmo.pk, "seccion": "ritmo_melodia"},
    )
    assert GroupBook.objects.get(libro=canciones).escalera == de_fabrica["Canción"]
    gb_ritmo = GroupBook.objects.get(libro=ritmo)
    assert gb_ritmo.escalera is None

    # Se cambia desde la pantalla de libros del grupo, y vacío la quita.
    client.post(
        reverse("clases:group_book_update", args=[gb_ritmo.pk]),
        {"escalera": de_fabrica["Lectura rítmica"].pk},
    )
    gb_ritmo.refresh_from_db()
    assert gb_ritmo.escalera == de_fabrica["Lectura rítmica"]
    client.post(reverse("clases:group_book_update", args=[gb_ritmo.pk]), {"escalera": ""})
    gb_ritmo.refresh_from_db()
    assert gb_ritmo.escalera is None

    # La pantalla ofrece las escaleras.
    r = client.get(reverse("clases:group_books_index", args=[grupo.pk]))
    assert "Sin escalera" in r.content.decode()
    assert "Lectura rítmica" in r.content.decode()


# =============================================================================
# C627 · Peldaños trabajados, siguiente y visto derivado
# =============================================================================


def test_siguiente_peldano_y_completar_da_por_visto(montaje):
    """C627."""
    gb, fila = montaje["gb"], _fila(montaje["gb"], "c1")

    item = escaleras.fijar(gb, fila["objeto"], fila["capitulo"], ["letra", "ritmo"])
    assert item.peldanos == ["letra", "ritmo"]
    assert item.siguiente_peldano() == "armonia"
    assert item.estado == GroupBookItem.PENDIENTE

    item = escaleras.fijar(gb, fila["objeto"], fila["capitulo"], montaje["cancion"].claves)
    assert item.estado == GroupBookItem.VISTO
    assert item.siguiente_peldano() is None

    # Quitar uno lo devuelve a la cola.
    item = escaleras.fijar(gb, fila["objeto"], fila["capitulo"], ["letra", "ritmo", "armonia"])
    assert item.estado == GroupBookItem.PENDIENTE
    assert item.siguiente_peldano() == "melodia"

    # Las claves que no son de la escalera no entran.
    item = escaleras.fijar(gb, fila["objeto"], fila["capitulo"], ["letra", "inventada"])
    assert item.peldanos == ["letra"]


def test_un_libro_sin_escalera_no_cambia_en_nada(client, montaje, profesor):
    """Anti-B. La afirmación de la fase 68, intacta: tratado no crea fila en el libro."""
    client.force_login(profesor)
    sesion = _sesion(profesor, montaje["grupo"])
    creados = libros_de_grupo.preparar_sesion(sesion, ["teoria"])
    assert len(creados) == 1 and creados[0].peldano == ""
    assert creados[0].escalera_en_clase() is None

    _tratar(client, creados[0], "si")
    _tratar(client, creados[0], "si", saltos=2)
    assert not GroupBookItem.objects.filter(group_book=montaje["gb_teoria"]).exists()
    creados[0].refresh_from_db()
    assert creados[0].tratado is True and creados[0].peldanos_anadidos == []
    assert escaleras.fijar(montaje["gb_teoria"], _fila(montaje["gb_teoria"], "t1")["objeto"], None, ["x"]) is None


# =============================================================================
# C628 · Preparar propone el primer no completado con su siguiente peldaño
# =============================================================================


def test_preparar_propone_el_primer_no_completado_con_su_peldano(montaje, profesor):
    """C628."""
    gb, grupo = montaje["gb"], montaje["grupo"]

    def propuesta():
        return [
            (f["titulo"], f["peldano"]["clave"] if f["peldano"] else None)
            for f in libros_de_grupo.previsualizar_sesion(grupo, ["cancion"])
        ]

    assert propuesta() == [("c1", "letra")]

    c1 = _fila(gb, "c1")
    escaleras.fijar(gb, c1["objeto"], c1["capitulo"], ["letra", "ritmo"])
    assert propuesta() == [("c1", "armonia")]

    sesion = _sesion(profesor, grupo)
    creados = libros_de_grupo.preparar_sesion(sesion, ["cancion"])
    assert [(i.get_content_title(), i.peldano) for i in creados] == [("c1", "armonia")]

    escaleras.fijar(gb, c1["objeto"], c1["capitulo"], montaje["cancion"].claves)
    assert propuesta() == [("c2", "letra")]

    # Dos a la vez, en peldaños independientes.
    c2 = _fila(gb, "c2")
    escaleras.fijar(gb, c2["objeto"], c2["capitulo"], ["letra"])
    dos = libros_de_grupo.previsualizar_sesion(grupo, ["cancion"], por_libro=2)
    assert [(f["titulo"], f["peldano"]["clave"]) for f in dos] == [("c2", "ritmo"), ("c3", "letra")]

    # Elegir a mano también lleva el peldaño.
    otra = _sesion(profesor, grupo)
    c3 = _fila(gb, "c3")
    elegidos = libros_de_grupo.anadir_elementos(otra, [(gb.pk, c3["tipo"].pk, c3["objeto"].pk)])
    assert elegidos[0].peldano == "letra"


def test_la_vista_previa_dice_el_paso(client, montaje, profesor):
    """C628, en pantalla: «paso 1 de 5: Letra y forma»."""
    client.force_login(profesor)
    sesion = _sesion(profesor, montaje["grupo"])
    r = client.get(reverse("clases:class_session_prepare_preview", args=[sesion.pk]))
    assert r.status_code == 200
    assert "paso 1 de 5: Letra y forma" in r.content.decode()


# =============================================================================
# C629 · Tratado sube uno, «+2» dos, y deshacer retira lo que puso
# =============================================================================


def test_tratado_sube_uno_por_defecto_y_dos_con_el_control(client, montaje, profesor):
    """C629."""
    client.force_login(profesor)
    gb, c1 = montaje["gb"], _fila(montaje["gb"], "c1")
    sesion = _sesion(profesor, montaje["grupo"])
    item = libros_de_grupo.preparar_sesion(sesion, ["cancion"])[0]

    _tratar(client, item, "si")
    assert _item_del_grupo(gb, c1).peldanos == ["letra"]
    item.refresh_from_db()
    assert item.tratado is True and item.peldanos_anadidos == ["letra"]

    # «+2» sobre el mismo toque: dos desde la misma base, no tres.
    _tratar(client, item, "si", saltos=2)
    assert _item_del_grupo(gb, c1).peldanos == ["letra", "ritmo"]
    item.refresh_from_db()
    assert item.peldanos_anadidos == ["letra", "ritmo"]

    # Desmarcar retira los dos; el elemento sigue pendiente.
    _tratar(client, item, "")
    assert _item_del_grupo(gb, c1).peldanos == []
    item.refresh_from_db()
    assert item.tratado is None and item.peldanos_anadidos == []

    # Saltado no sube nada.
    _tratar(client, item, "no")
    assert _item_del_grupo(gb, c1).peldanos == []

    # Más de dos no existe: cualquier valor que no sea «2» sube uno.
    _tratar(client, item, "si", saltos=3)
    assert _item_del_grupo(gb, c1).peldanos == ["letra"]


def test_completar_con_tratado_da_por_visto_y_deshacer_devuelve_a_la_cola(
    client, montaje, profesor
):
    """C629, el borde: el último peldaño por tratado ⇒ visto, con la sesión apuntada."""
    client.force_login(profesor)
    gb, c1 = montaje["gb"], _fila(montaje["gb"], "c1")
    escaleras.fijar(gb, c1["objeto"], c1["capitulo"], ["letra", "ritmo", "armonia", "melodia"])
    sesion = _sesion(profesor, montaje["grupo"])
    item = libros_de_grupo.preparar_sesion(sesion, ["cancion"])[0]
    assert item.peldano == "montaje"

    r = _tratar(client, item, "si")
    fila = _item_del_grupo(gb, c1)
    assert fila.estado == GroupBookItem.VISTO and fila.visto_en == sesion
    # En el último peldaño no hay «+2».
    assert "+2" not in r.content.decode()
    # Y ya no se propone.
    assert [f["titulo"] for f in libros_de_grupo.previsualizar_sesion(montaje["grupo"], ["cancion"])] == ["c2"]

    _tratar(client, item, "")
    fila.refresh_from_db()
    assert fila.estado == GroupBookItem.PENDIENTE and fila.visto_en is None
    assert fila.peldanos == ["letra", "ritmo", "armonia", "melodia"]


def test_el_boton_mas_dos_sale_cuando_quedan_dos(client, montaje, profesor):
    client.force_login(profesor)
    sesion = _sesion(profesor, montaje["grupo"])
    item = libros_de_grupo.preparar_sesion(sesion, ["cancion"])[0]
    r = _tratar(client, item, "no")
    assert "+2" in r.content.decode()


def test_el_visor_fija_hasta_un_peldano(client, montaje, profesor, django_user_model):
    """C629, la escalera del visor: «hemos llegado hasta aquí» es acumulativo."""
    client.force_login(profesor)
    gb, c1 = montaje["gb"], _fila(montaje["gb"], "c1")
    sesion = _sesion(profesor, montaje["grupo"])
    item = libros_de_grupo.preparar_sesion(sesion, ["cancion"])[0]
    _tratar(client, item, "si")

    url = reverse("clases:class_session_item_peldano", args=[item.pk])
    r = client.post(url, {"clave": "armonia"})
    assert r.status_code == 200
    datos = r.json()
    assert datos["hechos"] == 3 and datos["previsto"] == "melodia" and datos["puede_dos"] is True
    assert _item_del_grupo(gb, c1).peldanos == ["letra", "ritmo", "armonia"]
    # Lo fijado a mano manda: el toque de tratado ya no tiene nada que deshacer.
    item.refresh_from_db()
    assert item.peldanos_anadidos == []

    r = client.post(url, {"clave": ""})
    assert r.json()["hechos"] == 0
    assert _item_del_grupo(gb, c1).peldanos == []

    # Otro profesor, 404. Y un elemento sin escalera, 404.
    otro = django_user_model.objects.create_user(email="otro-esc@x.es", password="x", is_staff=True)
    client.force_login(otro)
    assert client.post(url, {"clave": "letra"}).status_code == 404
    client.force_login(profesor)
    sin = libros_de_grupo.preparar_sesion(sesion, ["teoria"])[0]
    assert client.post(reverse("clases:class_session_item_peldano", args=[sin.pk]), {"clave": "x"}).status_code == 404


def test_la_presentacion_lleva_la_escalera(client, montaje, profesor):
    client.force_login(profesor)
    sesion = _sesion(profesor, montaje["grupo"])
    libros_de_grupo.preparar_sesion(sesion, ["cancion", "teoria"])
    r = client.get(reverse("clases:class_session_present", args=[sesion.pk]))
    html = r.content.decode()
    assert '"escalera": {"nombre": "Canci' in html
    assert '"escalera": null' in html
    assert 'id="fab-dos"' in html and 'id="flyout-escalera"' in html


# =============================================================================
# C630 · Fijar el punto de partida desde los libros del grupo
# =============================================================================


def test_las_casillas_de_la_escalera_en_el_libro_del_grupo(client, montaje, profesor):
    """C630."""
    client.force_login(profesor)
    gb, c1 = montaje["gb"], _fila(montaje["gb"], "c1")
    r = client.get(reverse("clases:group_book_items", args=[gb.pk]))
    html = r.content.decode()
    assert html.count('"campo": "peldano"') == 3 * 5  # tres elementos, cinco peldaños
    assert "2 Patrón rítmico (groove)" in html

    url = reverse("clases:group_book_item_toggle", args=[gb.pk])
    base = {"content_type": c1["tipo"].pk, "object_id": c1["objeto"].pk, "campo": "peldano"}
    for clave in ["letra", "ritmo", "armonia", "melodia"]:
        r = client.post(url, {**base, "clave": clave})
        assert r.status_code == 200
    assert _item_del_grupo(gb, c1).peldanos == ["letra", "ritmo", "armonia", "melodia"]
    assert _item_del_grupo(gb, c1).estado == GroupBookItem.PENDIENTE

    r = client.post(url, {**base, "clave": "montaje"})
    assert _item_del_grupo(gb, c1).estado == GroupBookItem.VISTO
    assert "visto" in r.content.decode()

    # Desmarcar uno lo devuelve.
    client.post(url, {**base, "clave": "ritmo"})
    fila = _item_del_grupo(gb, c1)
    assert fila.peldanos == ["letra", "armonia", "melodia", "montaje"]
    assert fila.estado == GroupBookItem.PENDIENTE

    # Sin escalera, la casilla no hace nada.
    t1 = _fila(montaje["gb_teoria"], "t1")
    client.post(
        reverse("clases:group_book_item_toggle", args=[montaje["gb_teoria"].pk]),
        {"content_type": t1["tipo"].pk, "object_id": t1["objeto"].pk, "campo": "peldano", "clave": "letra"},
    )
    assert not GroupBookItem.objects.filter(group_book=montaje["gb_teoria"]).exists()


# =============================================================================
# C631 · El guión
# =============================================================================


def test_el_guion_va_entre_comenzar_y_editar_y_dice_los_pasos(client, montaje, profesor):
    """C631."""
    client.force_login(profesor)
    gb = montaje["gb"]
    # c2 empezado y fuera de la clase de hoy: tiene que salir en «Dónde va».
    c2 = _fila(gb, "c2")
    escaleras.fijar(gb, c2["objeto"], c2["capitulo"], ["letra", "ritmo"])
    sesion = _sesion(profesor, montaje["grupo"])
    libros_de_grupo.preparar_sesion(sesion, ["teoria", "cancion"])

    r = client.get(reverse("clases:class_session_view", args=[sesion.pk]))
    html = r.content.decode()
    assert html.index("Comenzar clase") < html.index("📋 Guión") < html.index("Editar\n")
    assert 'id="guion"' in html

    modal = html[html.index('<dialog id="guion"'):]
    # Secciones en el orden de la clase: teoría antes que canciones.
    assert modal.index(">Teoría<") < modal.index(">Canciones<")
    assert "paso 1 de 5: Letra y forma" in modal
    # El elemento de teoría no tiene escalera: ningún «paso» antes de la sección de canciones.
    assert "paso " not in modal[: modal.index(">Canciones<")]
    # Dónde va el grupo: c2 con 2 de 5, siguiente la armonía; c1 (en la clase) no.
    donde = modal[modal.index("Dónde va"):]
    assert "c2" in donde and "2 de 5" in donde and "siguiente: Progresión armónica" in donde
    assert "c1" not in donde


def test_el_alumnado_no_ve_el_guion(client, montaje, profesor, django_user_model):
    """C631. El botón y el modal son del profesor."""
    sesion = _sesion(profesor, montaje["grupo"])
    libros_de_grupo.preparar_sesion(sesion, ["cancion"])
    alumna = django_user_model.objects.create_user(email="alumna-esc@x.es", password="x")
    Enrollment.objects.create(user=alumna, group=montaje["grupo"], is_active=True)
    client.force_login(alumna)
    r = client.get(reverse("clases:class_session_view", args=[sesion.pk]))
    assert r.status_code == 200
    html = r.content.decode()
    assert "Guión" not in html and 'id="guion"' not in html


def test_el_guion_sin_elementos_no_rompe(client, montaje, profesor):
    client.force_login(profesor)
    sesion = _sesion(profesor, montaje["grupo"])
    r = client.get(reverse("clases:class_session_view", args=[sesion.pk]))
    assert r.status_code == 200
    assert "La clase no tiene elementos todavía" in r.content.decode()
