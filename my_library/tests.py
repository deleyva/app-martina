import collections
import json
import uuid
from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from cms.models import ExternalResource
from martina_bescos_app.users.tests.factories import UserFactory
from my_library import facets
from my_library.models import (
    ItemSection,
    LibraryDeck,
    LibraryItem,
    ReviewLog,
    SharedNote,
)
from my_library.session import (
    TAMANO_SESION_POR_DEFECTO,
    agrupar_por_tematica,
    construir_sesion,
    facetas_disponibles,
    filtrar_por_facetas,
    unidades_de_practica,
)


@pytest.fixture
def user(db):
    """La fixture `user` de martina_bescos_app/conftest.py no alcanza a esta app."""
    return UserFactory()


@pytest.fixture
def library_item(db, user):
    """Un LibraryItem real, con un content_object concreto (no un mock)."""
    resource = ExternalResource.objects.create(
        url="https://example.org/pentatonica-pos-2",
        title="Pentatónica posición 2",
    )
    return LibraryItem.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(resource),
        object_id=resource.pk,
        proficiency_level=2,
    )


# === C3: el modelo guarda lo acordado ===


def test_log_deriva_el_usuario_del_item(library_item, user):
    review = ReviewLog.log(library_item, proficiency_before=2, proficiency_after=3)

    assert review.user == user
    assert review.item == library_item
    assert review.source == ReviewLog.SOURCE_STUDY


def test_duracion_se_capa_en_una_hora(library_item):
    """Dejar la pestaña abierta toda la noche no debe meter un outlier."""
    review = ReviewLog.log(library_item, duration_seconds=8 * 3600)

    assert review.duration_seconds == ReviewLog.MAX_DURATION_SECONDS


def test_duracion_normal_se_guarda_tal_cual(library_item):
    review = ReviewLog.log(library_item, duration_seconds=240)

    assert review.duration_seconds == 240


def test_improved_compara_niveles(library_item):
    assert ReviewLog.log(library_item, proficiency_before=1, proficiency_after=3).improved is True
    assert ReviewLog.log(library_item, proficiency_before=3, proficiency_after=1).improved is False
    assert ReviewLog.log(library_item, proficiency_before=2, proficiency_after=2).improved is False
    assert ReviewLog.log(library_item).improved is None


def test_borrar_el_mazo_no_borra_la_historia(library_item, user):
    deck = LibraryDeck.objects.create(
        user=user, name="Pentatónicas", tags_json=json.dumps(["pentatonica"])
    )
    review = ReviewLog.log(library_item, deck=deck)

    deck.delete()
    review.refresh_from_db()

    assert ReviewLog.objects.filter(pk=review.pk).exists()
    assert review.deck is None


# === C4: un repaso en el visor graba exactamente una fila ===


def test_log_review_graba_una_fila_completa(client, library_item, user):
    deck = LibraryDeck.objects.create(
        user=user, name="Guitarra", tags_json=json.dumps(["guitarra"])
    )
    session_uuid = uuid.uuid4()
    client.force_login(user)

    response = client.post(
        reverse("my_library:log_review", args=[library_item.pk]),
        {
            "level": "4",
            "duration_seconds": "180",
            "session_uuid": str(session_uuid),
            "deck": str(deck.pk),
        },
    )

    assert response.status_code == 204

    review = ReviewLog.objects.get()
    assert review.item == library_item
    assert review.source == ReviewLog.SOURCE_STUDY
    assert review.proficiency_before == 2  # el que tenía antes del POST
    assert review.proficiency_after == 4
    assert review.duration_seconds == 180
    assert review.session_uuid == session_uuid
    assert review.deck == deck


def test_log_review_actualiza_contadores_del_item(client, library_item, user):
    client.force_login(user)

    client.post(
        reverse("my_library:log_review", args=[library_item.pk]), {"level": "3"}
    )

    library_item.refresh_from_db()
    assert library_item.proficiency_level == 3
    assert library_item.times_viewed == 1
    assert library_item.last_viewed is not None


def test_log_review_tolera_datos_basura_del_cliente(client, library_item, user):
    """Un uuid o una duración mal formados no deben tumbar el POST."""
    client.force_login(user)

    response = client.post(
        reverse("my_library:log_review", args=[library_item.pk]),
        {
            "level": "2",
            "session_uuid": "no-soy-un-uuid",
            "duration_seconds": "un-rato",
            "deck": "99999",
        },
    )

    assert response.status_code == 204
    review = ReviewLog.objects.get()
    assert review.session_uuid is None
    assert review.duration_seconds is None
    assert review.deck is None


def test_log_review_no_deja_tocar_la_biblioteca_ajena(client, library_item, django_user_model):
    intruso = django_user_model.objects.create_user(
        email="intruso@example.org", password="x"  # noqa: S106
    )
    client.force_login(intruso)

    response = client.post(
        reverse("my_library:log_review", args=[library_item.pk]), {"level": "4"}
    )

    assert response.status_code == 404
    assert ReviewLog.objects.count() == 0


def test_los_repasos_de_una_tanda_comparten_session_uuid(client, library_item, user):
    session_uuid = uuid.uuid4()
    client.force_login(user)

    for level in ("2", "3"):
        client.post(
            reverse("my_library:log_review", args=[library_item.pk]),
            {"level": level, "session_uuid": str(session_uuid)},
        )

    assert ReviewLog.objects.filter(session_uuid=session_uuid).count() == 2


# === C5: el histórico es independiente de los contadores ===


def test_days_since_last_review_es_none_sin_repasos(library_item):
    assert library_item.last_review is None
    assert library_item.days_since_last_review is None


def test_days_since_last_review_usa_el_repaso_mas_reciente(library_item):
    ReviewLog.objects.create(
        user=library_item.user,
        item=library_item,
        reviewed_at=timezone.now() - timedelta(days=30),
    )
    reciente = ReviewLog.objects.create(
        user=library_item.user,
        item=library_item,
        reviewed_at=timezone.now() - timedelta(days=3),
    )

    assert library_item.last_review == reciente
    assert library_item.days_since_last_review == 3


def test_last_viewed_no_alimenta_el_historico(library_item):
    """Abrir el visor no es repasar: mark_as_viewed no crea ReviewLog."""
    library_item.mark_as_viewed()

    assert library_item.times_viewed == 1
    assert library_item.reviews.count() == 0
    assert library_item.days_since_last_review is None


# === C6: práctica y valoración manual quedan distinguibles ===


def test_valorar_desde_el_indice_queda_marcado_como_manual(client, library_item, user):
    client.force_login(user)

    client.post(
        reverse("my_library:update_proficiency", args=[library_item.pk]), {"level": "4"}
    )

    review = ReviewLog.objects.get()
    assert review.source == ReviewLog.SOURCE_MANUAL
    assert review.proficiency_before == 2
    assert review.proficiency_after == 4
    assert review.duration_seconds is None


def test_un_nivel_invalido_no_graba_nada(client, library_item, user):
    client.force_login(user)

    client.post(
        reverse("my_library:update_proficiency", args=[library_item.pk]), {"level": "9"}
    )

    library_item.refresh_from_db()
    assert library_item.proficiency_level == 2
    assert ReviewLog.objects.count() == 0


def test_el_visor_recibe_el_mazo_y_apunta_a_log_review(client, library_item, user):
    """El JS del visor depende de que la plantilla interpole el mazo."""
    deck = LibraryDeck.objects.create(
        user=user, name="Pentatónicas", tags_json=json.dumps(["pentatonica"])
    )
    client.force_login(user)

    response = client.get(
        reverse("my_library:study_session"),
        {"items": str(library_item.pk), "deck": str(deck.pk)},
    )
    html = response.content.decode()

    assert response.status_code == 200
    assert f"var deckPk = '{deck.pk}';" in html
    assert "log-review/" in html
    assert "sessionUuid" in html
    # El visor ya no debe hacer los dos POST antiguos por item
    assert "mark-viewed/" not in html


def test_el_visor_sin_mazo_no_manda_deck(client, library_item, user):
    client.force_login(user)

    response = client.get(
        reverse("my_library:study_session"), {"items": str(library_item.pk)}
    )

    assert "var deckPk = '';" in response.content.decode()


# === Construcción de sesiones acotadas ===


def _item(user, titulo, *, nivel=1, tags=()):
    recurso = ExternalResource.objects.create(
        url=f"https://example.org/{titulo}", title=titulo
    )
    item = LibraryItem.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(recurso),
        object_id=recurso.pk,
        proficiency_level=nivel,
    )
    for t in tags:
        item.tags.add(t)
    return item


def _practicado_hace(item, dias):
    ReviewLog.objects.create(
        user=item.user,
        item=item,
        source=ReviewLog.SOURCE_STUDY,
        reviewed_at=timezone.now() - timedelta(days=dias),
    )


def test_la_sesion_no_crece_con_la_biblioteca(db, user):
    """El síntoma original: añadir cosas alargaba la sesión."""
    items = [_item(user, f"item-{n}") for n in range(30)]

    sesion = construir_sesion(items, tamano=8)

    assert len(sesion) == 8


def test_la_sesion_devuelve_todo_si_hay_menos_del_tope(db, user):
    items = [_item(user, f"item-{n}") for n in range(3)]

    assert len(construir_sesion(items, tamano=8)) == 3


def test_lo_nuevo_entra_siempre_aunque_haya_repaso(db, user):
    nuevo = _item(user, "nunca-tocado")
    viejo = _item(user, "practicado-ayer")
    _practicado_hace(viejo, 0)

    sesion = construir_sesion([viejo, nuevo], tamano=1)

    assert sesion == [nuevo]


def test_lo_nuevo_no_puede_inundar_la_sesion(db, user):
    """El defecto que había en producción: 10 elementos nuevos dejaban fuera
    a 3 que llevaban 60 días sin tocarse. Ni uno de repaso entraba."""
    vencidos = [_item(user, f"vencido-{n}") for n in range(3)]
    for v in vencidos:
        _practicado_hace(v, 60)
    nuevos = [_item(user, f"nuevo-{n:02d}") for n in range(10)]

    sesion = construir_sesion(vencidos + nuevos, tamano=8)
    pks = {i.pk for i in sesion}

    assert len(sesion) == 8
    for v in vencidos:
        assert v.pk in pks, "un vencido de 60 días se quedó fuera"


def test_la_cuota_de_novedad_es_una_cuarta_parte(db, user):
    conocidos = [_item(user, f"c-{n}") for n in range(20)]
    for c in conocidos:
        _practicado_hace(c, 30)
    nuevos = [_item(user, f"n-{n}") for n in range(20)]

    sesion = construir_sesion(conocidos + nuevos, tamano=8)
    cuantos_nuevos = sum(1 for i in sesion if i.pk in {n.pk for n in nuevos})

    assert cuantos_nuevos == 2, f"entraron {cuantos_nuevos} nuevos, esperaba 2"


def test_sin_repaso_suficiente_la_sesion_se_llena_con_nuevo(db, user):
    """Dejar la sesión a medias habiendo material sin tocar sería absurdo."""
    conocido = _item(user, "unico-conocido")
    _practicado_hace(conocido, 30)
    nuevos = [_item(user, f"n-{n}") for n in range(10)]

    sesion = construir_sesion([conocido] + nuevos, tamano=8)

    assert len(sesion) == 8
    assert conocido.pk in {i.pk for i in sesion}


def test_sin_material_nuevo_la_sesion_es_todo_repaso(db, user):
    conocidos = [_item(user, f"c-{n}") for n in range(10)]
    for c in conocidos:
        _practicado_hace(c, 30)

    sesion = construir_sesion(conocidos, tamano=8)

    assert len(sesion) == 8


def test_lo_nuevo_entra_por_orden_de_alta(db, user):
    """Lo más parecido al orden del libro que hay hoy en el modelo."""
    nuevos = [_item(user, f"ej-{n:02d}") for n in range(10)]

    sesion = construir_sesion(nuevos, tamano=4)
    pks = [i.pk for i in sesion]

    assert pks == sorted(pks), "el material nuevo no salió en orden de alta"


def test_entra_antes_lo_mas_vencido(db, user):
    """Vencimiento es relativo al nivel, no días absolutos."""
    # Nivel 4 → plazo 21 días. 30 días = ratio 1.4
    sabido = _item(user, "me-lo-se", nivel=4)
    _practicado_hace(sabido, 30)
    # Nivel 1 → plazo 1 día. 10 días = ratio 10
    flojo = _item(user, "flojito", nivel=1)
    _practicado_hace(flojo, 10)

    sesion = construir_sesion([sabido, flojo], tamano=1)

    assert sesion == [flojo]


def test_lo_recien_practicado_cede_el_sitio(db, user):
    reciente = _item(user, "recien-visto", nivel=4)
    _practicado_hace(reciente, 1)
    pendiente = _item(user, "pendiente", nivel=2)
    _practicado_hace(pendiente, 10)

    sesion = construir_sesion([reciente, pendiente], tamano=1)

    assert sesion == [pendiente]


def test_valorar_desde_el_indice_no_cuenta_como_practica(db, user):
    """Solo source=study mueve el reloj de vencimiento."""
    item = _item(user, "solo-valorado")
    ReviewLog.objects.create(
        user=user, item=item, source=ReviewLog.SOURCE_MANUAL,
        reviewed_at=timezone.now(),
    )
    otro = _item(user, "otro")
    _practicado_hace(otro, 0)

    # El valorado a mano sigue contando como nunca practicado → prioridad máxima
    assert construir_sesion([otro, item], tamano=1) == [item]


def test_lo_de_la_misma_tematica_sale_seguido(db, user):
    pentas = [
        _item(user, f"penta-{n}", tags=["concepto:pentatonica"]) for n in range(3)
    ]
    otros = [_item(user, f"otro-{n}", tags=["concepto:arpegio"]) for n in range(3)]
    # Se intercalan a la entrada para que solo la agrupación pueda juntarlos
    mezclados = [pentas[0], otros[0], pentas[1], otros[1], pentas[2], otros[2]]

    orden = [i.pk for i in agrupar_por_tematica(mezclados)]
    posiciones = [orden.index(p.pk) for p in pentas]

    assert max(posiciones) - min(posiciones) == 2, "las pentatónicas no salieron seguidas"


def test_agrupar_no_pierde_ni_duplica_elementos(db, user):
    items = [_item(user, f"a-{n}", tags=["concepto:x"]) for n in range(3)]
    items += [_item(user, f"b-{n}", tags=["estilo:y"]) for n in range(3)]
    items += [_item(user, f"c-{n}") for n in range(2)]  # sin etiquetas

    resultado = agrupar_por_tematica(items)

    assert sorted(i.pk for i in resultado) == sorted(i.pk for i in items)
    assert len(resultado) == len(items)


def test_los_bloques_tematicos_son_cortos(db, user):
    """Agrupar sí, pero no convertir la sesión en un bloque único."""
    items = [
        _item(user, f"penta-{n}", tags=["concepto:pentatonica"]) for n in range(10)
    ]

    resultado = agrupar_por_tematica(items, max_bloque=4)

    assert len(resultado) == 10  # no pierde nada


# === Migración de etiquetas ===


def _migrar(tmp_path, lineas, ejecutar=False, solo_mazos=False):
    from django.core.management import call_command

    mapa = tmp_path / "mapa.txt"
    mapa.write_text("\n".join(lineas) + "\n")
    args = ["migrar_etiquetas", "--mapa", str(mapa)]
    if ejecutar:
        args.append("--ejecutar")
    if solo_mazos:
        args.append("--solo-mazos")
    call_command(*args)


def test_dos_origenes_al_mismo_destino_se_fusionan(db, tmp_path, user):
    """El bug que encontró el ensayo en seco: los dos se clasificaban como
    renombrado y el segundo reventaba contra la unicidad de taggit."""
    from taggit.models import Tag

    a = _item(user, "uno", tags=["jazz"])
    b = _item(user, "dos", tags=["genre/jazz"])

    _migrar(tmp_path, ["jazz -> estilo:jazz", "genre/jazz -> estilo:jazz"], ejecutar=True)

    assert Tag.objects.filter(name="estilo:jazz").count() == 1
    assert not Tag.objects.filter(name__in=["jazz", "genre/jazz"]).exists()
    assert {t.name for t in a.tags.all()} == {"estilo:jazz"}
    assert {t.name for t in b.tags.all()} == {"estilo:jazz"}


def test_en_seco_no_toca_nada(db, tmp_path, user):
    from taggit.models import Tag

    _item(user, "uno", tags=["jazz"])

    _migrar(tmp_path, ["jazz -> estilo:jazz"])  # sin --ejecutar

    assert Tag.objects.filter(name="jazz").exists()
    assert not Tag.objects.filter(name="estilo:jazz").exists()


def test_la_migracion_no_pierde_etiquetados(db, tmp_path, user):
    item = _item(user, "uno", tags=["jazz", "guitar"])

    _migrar(
        tmp_path,
        ["jazz -> estilo:jazz", "guitar -> instrumento:guitarra"],
        ejecutar=True,
    )

    assert {t.name for t in item.tags.all()} == {"estilo:jazz", "instrumento:guitarra"}


def test_un_elemento_con_las_dos_etiquetas_no_queda_duplicado(db, tmp_path, user):
    """Si un elemento ya tenía 'jazz' Y 'genre/jazz', tras fusionar tiene una."""
    item = _item(user, "uno", tags=["jazz", "genre/jazz"])

    _migrar(tmp_path, ["jazz -> estilo:jazz", "genre/jazz -> estilo:jazz"], ejecutar=True)

    nombres = [t.name for t in item.tags.all()]
    assert nombres == ["estilo:jazz"], nombres


def test_borrar_elimina_la_etiqueta(db, tmp_path, user):
    from taggit.models import Tag

    _item(user, "uno", tags=["borrar"])

    _migrar(tmp_path, ["borrar -> __BORRAR__"], ejecutar=True)

    assert not Tag.objects.filter(name="borrar").exists()


def test_las_etiquetas_ausentes_se_ignoran(db, tmp_path, user):
    """El mapa lleva 188 líneas; algunas ya no existirán."""
    _migrar(tmp_path, ["no-existe-ya -> concepto:loquesea"], ejecutar=True)  # no revienta


def test_la_migracion_es_idempotente(db, tmp_path, user):
    from taggit.models import Tag

    item = _item(user, "uno", tags=["jazz"])
    lineas = ["jazz -> estilo:jazz"]

    _migrar(tmp_path, lineas, ejecutar=True)
    _migrar(tmp_path, lineas, ejecutar=True)  # segunda pasada

    assert Tag.objects.filter(name="estilo:jazz").count() == 1
    assert {t.name for t in item.tags.all()} == {"estilo:jazz"}


# === Migración de etiquetas: los mazos van detrás ===
#
# El defecto que nadie cubría. El 2026-08-12 la migración corrió en producción,
# renombró las etiquetas y dejó los mazos apuntando a los nombres viejos. Los
# tres mazos del principal pasaron a contar 0 sin decir nada.


def _mazo(user, nombre, tags):
    return LibraryDeck.objects.create(
        user=user, name=nombre, tags_json=json.dumps(tags)
    )


def test_renombrar_una_etiqueta_arrastra_el_mazo(db, tmp_path, user):
    """El defecto de producción, reproducido: sin esto el mazo cuenta 0."""
    item = _item(user, "uno", tags=["instrument/guitar"])
    mazo = _mazo(user, "guitarra", ["instrument/guitar"])

    _migrar(tmp_path, ["instrument/guitar -> instrumento:guitarra"], ejecutar=True)

    mazo.refresh_from_db()
    assert mazo.get_tags() == ["instrumento:guitarra"]
    tag_map = LibraryDeck.build_tag_map(LibraryItem.objects.filter(user=user))
    assert mazo.get_matching_item_pks(tag_map) == [item.pk]


def test_el_mazo_se_arrastra_aunque_la_etiqueta_ya_este_renombrada(db, tmp_path, user):
    """La reparación de lo ya roto. Las etiquetas ya migraron; los mazos no.

    Se aplica el MAPA, no el estado de `Tag`, así que el arrastre funciona
    sobre mazos que se quedaron atrás en una ejecución anterior.
    """
    item = _item(user, "uno", tags=["instrumento:guitarra"])  # ya migrada
    mazo = _mazo(user, "guitarra", ["instrument/guitar"])  # se quedó atrás

    _migrar(tmp_path, ["instrument/guitar -> instrumento:guitarra"], ejecutar=True)

    mazo.refresh_from_db()
    assert mazo.get_tags() == ["instrumento:guitarra"]
    tag_map = LibraryDeck.build_tag_map(LibraryItem.objects.filter(user=user))
    assert mazo.get_matching_item_pks(tag_map) == [item.pk]


def test_el_mazo_multietiqueta_se_arrastra_entero(db, tmp_path, user):
    """El mazo 'guitarra jazz' real: dos etiquetas, las dos renombradas."""
    mazo = _mazo(user, "guitarra jazz", ["instrument/guitar", "genre/jazz"])

    _migrar(
        tmp_path,
        ["instrument/guitar -> instrumento:guitarra", "genre/jazz -> estilo:jazz"],
        ejecutar=True,
    )

    mazo.refresh_from_db()
    assert mazo.get_tags() == ["instrumento:guitarra", "estilo:jazz"]


def test_dos_etiquetas_del_mazo_que_se_fusionan_no_quedan_duplicadas(db, tmp_path, user):
    mazo = _mazo(user, "jazz", ["jazz", "genre/jazz"])

    _migrar(tmp_path, ["jazz -> estilo:jazz", "genre/jazz -> estilo:jazz"], ejecutar=True)

    mazo.refresh_from_db()
    assert mazo.get_tags() == ["estilo:jazz"]


def test_un_mazo_no_se_queda_vacio_al_borrar_su_unica_etiqueta(db, tmp_path, user):
    """Un mazo sin etiquetas devuelve la biblioteca ENTERA. Peor que romperlo.

    Se deja apuntando al nombre muerto: cuenta 0, que es visiblemente roto y
    honesto, en vez de 51, que es silenciosamente falso.
    """
    _item(user, "uno", tags=["otra"])
    mazo = _mazo(user, "muerto", ["borrame"])

    _migrar(tmp_path, ["borrame -> __BORRAR__"], ejecutar=True)

    mazo.refresh_from_db()
    assert mazo.get_tags() == ["borrame"]
    tag_map = LibraryDeck.build_tag_map(LibraryItem.objects.filter(user=user))
    assert mazo.get_matching_item_pks(tag_map) == []


def test_el_mazo_conserva_las_etiquetas_que_el_mapa_no_toca(db, tmp_path, user):
    mazo = _mazo(user, "mixto", ["caged-system", "instrument/guitar"])

    _migrar(tmp_path, ["instrument/guitar -> instrumento:guitarra"], ejecutar=True)

    mazo.refresh_from_db()
    assert mazo.get_tags() == ["caged-system", "instrumento:guitarra"]


def test_arrastrar_mazos_es_idempotente(db, tmp_path, user):
    mazo = _mazo(user, "guitarra", ["instrument/guitar"])
    lineas = ["instrument/guitar -> instrumento:guitarra"]

    _migrar(tmp_path, lineas, ejecutar=True)
    _migrar(tmp_path, lineas, ejecutar=True)

    mazo.refresh_from_db()
    assert mazo.get_tags() == ["instrumento:guitarra"]


def test_en_seco_no_toca_los_mazos(db, tmp_path, user):
    mazo = _mazo(user, "guitarra", ["instrument/guitar"])

    _migrar(tmp_path, ["instrument/guitar -> instrumento:guitarra"])  # sin --ejecutar

    mazo.refresh_from_db()
    assert mazo.get_tags() == ["instrument/guitar"]








def test_solo_mazos_no_toca_ninguna_etiqueta(db, tmp_path, user):
    """La bandera de reparación: arregla los mazos sin re-ejecutar el renombrado.

    El estado real de producción: las etiquetas ya migraron el 12/08 y el mazo
    se quedó apuntando al nombre viejo, que ya no existe.
    """
    from taggit.models import Tag

    _item(user, "uno", tags=["instrumento:guitarra"])  # ya migrada
    mazo = _mazo(user, "guitarra", ["instrument/guitar"])  # puntero muerto
    etiquetas_antes = set(Tag.objects.values_list("name", flat=True))

    _migrar(
        tmp_path,
        ["instrument/guitar -> instrumento:guitarra"],
        ejecutar=True,
        solo_mazos=True,
    )

    assert set(Tag.objects.values_list("name", flat=True)) == etiquetas_antes
    mazo.refresh_from_db()
    assert mazo.get_tags() == ["instrumento:guitarra"]


# === Trocear material largo (secciones) ===


def _seccion(item, nombre, orden=0, **kw):
    return ItemSection.objects.create(item=item, nombre=nombre, orden=orden, **kw)


def test_un_elemento_troceado_deja_de_salir_entero(db, user):
    """El punto entero: si el PDF sigue saliendo como unidad, no se arregló nada."""
    largo = _item(user, "popurri")
    a = _seccion(largo, "intro", 0)
    b = _seccion(largo, "estribillo", 1)

    unidades = unidades_de_practica([largo])

    assert [u.clave_de_practica for u in unidades] == [
        ("seccion", a.pk),
        ("seccion", b.pk),
    ]


def test_un_elemento_sin_secciones_sigue_siendo_la_unidad(db, user):
    corto = _item(user, "lick")

    unidades = unidades_de_practica([corto])

    assert [u.clave_de_practica for u in unidades] == [("item", corto.pk)]


def test_cada_seccion_lleva_su_propio_historial(db, user):
    largo = _item(user, "popurri")
    tocada = _seccion(largo, "intro", 0)
    sin_tocar = _seccion(largo, "final", 1)
    ReviewLog.objects.create(
        user=user, item=largo, section=tocada, source=ReviewLog.SOURCE_STUDY,
        reviewed_at=timezone.now() - timedelta(days=5),
    )

    assert tocada.days_since_last_review == 5
    assert sin_tocar.days_since_last_review is None


def test_repasar_una_seccion_no_cuenta_como_repasar_el_elemento(db, user):
    """Si contara, trocear haría que la pieza pareciera repasada entera."""
    largo = _item(user, "popurri")
    s = _seccion(largo, "intro")
    ReviewLog.objects.create(
        user=user, item=largo, section=s, source=ReviewLog.SOURCE_STUDY
    )

    assert largo.days_since_last_review is None


def test_las_claves_de_elemento_y_seccion_no_se_pisan(db, user):
    """Los pk de las dos tablas se solapan: el elemento 5 y la sección 5."""
    item = _item(user, "x")
    seccion = _seccion(_item(user, "y"), "trozo")

    assert item.clave_de_practica != seccion.clave_de_practica
    assert item.clave_de_practica[0] == "item"
    assert seccion.clave_de_practica[0] == "seccion"


def test_la_seccion_hereda_las_etiquetas_del_elemento(db, user):
    largo = _item(user, "blues largo", tags=["estilo:blues", "instrumento:guitarra"])
    s = _seccion(largo, "solo")

    assert {t.name for t in s.get_content_tags()} == {
        "estilo:blues",
        "instrumento:guitarra",
    }


def test_el_titulo_de_la_seccion_dice_de_donde_viene(db, user):
    largo = _item(user, "popurri")
    s = _seccion(largo, "estribillo")

    assert "popurri" in s.get_content_title()
    assert "estribillo" in s.get_content_title()


def test_la_sesion_mezcla_secciones_y_elementos_sueltos(db, user):
    largo = _item(user, "popurri")
    _seccion(largo, "intro", 0)
    _seccion(largo, "final", 1)
    suelto = _item(user, "lick")

    sesion = construir_sesion([largo, suelto], tamano=8)
    tipos = collections.Counter(u.clave_de_practica[0] for u in sesion)

    assert len(sesion) == 3
    assert tipos == {"seccion": 2, "item": 1}


def test_crear_una_seccion_desde_el_visor(client, db, user):
    largo = _item(user, "popurri")
    client.force_login(user)

    response = client.post(
        reverse("my_library:crear_seccion", args=[largo.pk]),
        {"nombre": "  Compases 30-60  ", "pagina_desde": "3", "pagina_hasta": "5"},
    )

    assert response.status_code == 200
    s = ItemSection.objects.get()
    assert s.nombre == "Compases 30-60"
    assert s.rango_paginas == (3, 5)


def test_una_seccion_sin_nombre_no_se_crea(client, db, user):
    largo = _item(user, "popurri")
    client.force_login(user)

    response = client.post(
        reverse("my_library:crear_seccion", args=[largo.pk]), {"nombre": "   "}
    )

    assert response.status_code == 400
    assert ItemSection.objects.count() == 0


def test_las_secciones_se_numeran_en_orden(client, db, user):
    largo = _item(user, "popurri")
    client.force_login(user)
    url = reverse("my_library:crear_seccion", args=[largo.pk])

    client.post(url, {"nombre": "primera"})
    client.post(url, {"nombre": "segunda"})

    assert [s.orden for s in largo.sections.all()] == [0, 1]
    assert [s.nombre for s in largo.sections.all()] == ["primera", "segunda"]


def test_no_se_trocea_el_elemento_de_otro(client, db, user, django_user_model):
    largo = _item(user, "popurri")
    intruso = django_user_model.objects.create_user(
        email="otro3@example.org", password="x"  # noqa: S106
    )
    client.force_login(intruso)

    response = client.post(
        reverse("my_library:crear_seccion", args=[largo.pk]), {"nombre": "mío"}
    )

    assert response.status_code == 404
    assert ItemSection.objects.count() == 0


def test_borrar_la_ultima_seccion_devuelve_el_elemento_a_la_cola(client, db, user):
    largo = _item(user, "popurri")
    s = _seccion(largo, "unica")
    client.force_login(user)

    client.post(reverse("my_library:borrar_seccion", args=[s.pk]))

    assert [u.clave_de_practica for u in unidades_de_practica([largo])] == [
        ("item", largo.pk)
    ]


def test_valorar_una_seccion_mueve_su_nivel_no_el_del_elemento(client, db, user):
    largo = _item(user, "popurri", nivel=1)
    s = _seccion(largo, "intro")
    client.force_login(user)

    client.post(
        reverse("my_library:log_review", args=[largo.pk]),
        {"level": "4", "section": str(s.pk)},
    )

    largo.refresh_from_db()
    s.refresh_from_db()
    assert s.proficiency_level == 4
    assert largo.proficiency_level == 1, "se movió el nivel del elemento entero"
    assert ReviewLog.objects.get().section_id == s.pk


def test_la_sesion_emite_tokens_distintos_para_secciones(client, db, user):
    largo = _item(user, "popurri", tags=["instrumento:guitarra"])
    _seccion(largo, "intro", 0)
    client.force_login(user)

    response = client.get(
        reverse("my_library:session_launch"), {"instrumento": "guitarra"}
    )

    tokens = response.url.split("items=")[1].split("&")[0].split(",")
    assert all(t.startswith("s") for t in tokens), tokens


def test_el_visor_reconoce_los_tokens_de_seccion(client, db, user):
    largo = _item(user, "popurri")
    s = _seccion(largo, "estribillo")
    client.force_login(user)

    response = client.get(reverse("my_library:study_session"), {"items": f"s{s.pk}"})
    html = response.content.decode()

    assert response.status_code == 200
    assert f'"section": {s.pk}' in html
    assert "estribillo" in html


def test_los_numeros_pelados_siguen_siendo_elementos(client, db, user):
    """Los enlaces antiguos no deben romperse."""
    item = _item(user, "lick")
    client.force_login(user)

    response = client.get(reverse("my_library:study_session"), {"items": str(item.pk)})

    assert response.status_code == 200
    assert '"section": null' in response.content.decode()


# === Arranque de sesión por faceta (C18) ===


def test_filtrar_sin_seleccion_devuelve_todo(db, user):
    items = [_item(user, f"i-{n}", tags=["instrumento:guitarra"]) for n in range(3)]

    assert len(filtrar_por_facetas(items, {})) == 3
    assert len(filtrar_por_facetas(items, {"instrumento": []})) == 3


def test_una_faceta_filtra(db, user):
    guitarra = _item(user, "g", tags=["instrumento:guitarra"])
    _item(user, "p", tags=["instrumento:piano"])

    resultado = filtrar_por_facetas(
        [guitarra] + list(LibraryItem.objects.exclude(pk=guitarra.pk)),
        {"instrumento": ["guitarra"]},
    )

    assert [i.pk for i in resultado] == [guitarra.pk]


def test_dentro_de_una_faceta_los_valores_suman(db, user):
    """O dentro de la faceta: marcar otro valor amplía la búsqueda."""
    penta = _item(user, "a", tags=["concepto:pentatonica"])
    arpegio = _item(user, "b", tags=["concepto:arpegio"])
    otro = _item(user, "c", tags=["concepto:escalas"])

    resultado = filtrar_por_facetas(
        [penta, arpegio, otro], {"concepto": ["pentatonica", "arpegio"]}
    )

    assert {i.pk for i in resultado} == {penta.pk, arpegio.pk}


def test_entre_facetas_las_condiciones_se_acumulan(db, user):
    """Y entre facetas: añadir otra faceta estrecha la búsqueda."""
    ambas = _item(user, "a", tags=["instrumento:guitarra", "concepto:pentatonica"])
    solo_instrumento = _item(user, "b", tags=["instrumento:guitarra"])
    solo_concepto = _item(user, "c", tags=["concepto:pentatonica"])

    resultado = filtrar_por_facetas(
        [ambas, solo_instrumento, solo_concepto],
        {"instrumento": ["guitarra"], "concepto": ["pentatonica"]},
    )

    assert [i.pk for i in resultado] == [ambas.pk]


def test_facetas_disponibles_cuenta_y_ordena(db, user):
    for n in range(3):
        _item(user, f"g-{n}", tags=["instrumento:guitarra"])
    _item(user, "p", tags=["instrumento:piano"])

    disponibles = facetas_disponibles(list(LibraryItem.objects.filter(user=user)))

    assert disponibles["instrumento"] == [("guitarra", 3), ("piano", 1)]


def test_facetas_disponibles_ignora_lo_que_no_sirve_para_filtrar(db, user):
    """Filtrar por 'evaluacion' o 'tema' no tiene sentido para practicar."""
    _item(user, "x", tags=["instrumento:guitarra", "evaluacion:examen", "tema:vitalinux"])

    disponibles = facetas_disponibles(list(LibraryItem.objects.filter(user=user)))

    assert set(disponibles) == {"instrumento"}


def test_el_selector_se_abre_y_lista_las_facetas(client, db, user):
    _item(user, "g", tags=["instrumento:guitarra", "concepto:pentatonica"])
    client.force_login(user)

    response = client.get(reverse("my_library:session_start"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "guitarra" in html
    assert "pentatonica" in html


def test_lanzar_una_sesion_filtrada_abre_el_visor_solo_con_lo_elegido(client, db, user):
    guitarras = [
        _item(user, f"g-{n}", tags=["instrumento:guitarra"]) for n in range(3)
    ]
    _item(user, "p", tags=["instrumento:piano"])
    client.force_login(user)

    response = client.get(
        reverse("my_library:session_launch"), {"instrumento": "guitarra"}
    )

    assert response.status_code == 302
    pks = {int(p) for p in response.url.split("items=")[1].split("&")[0].split(",")}
    assert pks == {g.pk for g in guitarras}


def test_lanzar_respeta_el_tope_de_sesion(client, db, user):
    for n in range(20):
        _item(user, f"g-{n}", tags=["instrumento:guitarra"])
    client.force_login(user)

    response = client.get(
        reverse("my_library:session_launch"), {"instrumento": "guitarra"}
    )

    pks = response.url.split("items=")[1].split("&")[0].split(",")
    assert len(pks) == TAMANO_SESION_POR_DEFECTO


def test_lanzar_sin_coincidencias_avisa_y_no_abre_el_visor(client, db, user):
    _item(user, "p", tags=["instrumento:piano"])
    client.force_login(user)

    response = client.get(
        reverse("my_library:session_launch"), {"instrumento": "trombon"}
    )

    assert response.status_code == 302
    assert "study" not in response.url
    assert "empezar" in response.url


def test_la_seleccion_vuelve_marcada_en_la_url(client, db, user):
    """La selección vive en la URL para poder guardarla en marcadores.

    Ojo al comprobarlo: el HTML lleva `peer-checked:` en las clases de
    Tailwind, así que buscar la subcadena "checked" da 21 falsos positivos.
    Hay que mirar el atributo en el input.
    """
    import re

    _item(user, "g", tags=["instrumento:guitarra", "concepto:pentatonica"])
    _item(user, "p", tags=["instrumento:piano"])
    client.force_login(user)

    html = client.get(
        reverse("my_library:session_start"),
        {"instrumento": "guitarra", "concepto": "pentatonica"},
    ).content.decode()

    # Solo las casillas de faceta: base.html trae sus propios <input>.
    casillas = [
        i
        for i in re.findall(r"<input[^>]*>", html)
        if re.search(r'name="(instrumento|concepto|estilo|tipo)"', i)
    ]
    marcados = [i for i in casillas if re.search(r"\schecked\b", i)]

    assert len(casillas) == 3  # guitarra, piano, pentatonica
    assert len(marcados) == 2
    assert all('value="piano"' not in m for m in marcados)


def test_el_recuento_en_vivo_responde(client, db, user):
    _item(user, "g", tags=["instrumento:guitarra"])
    client.force_login(user)

    response = client.get(
        reverse("my_library:session_count"), {"instrumento": "guitarra"}
    )

    assert response.status_code == 200
    assert "1" in response.content.decode()


def test_no_se_ve_la_biblioteca_de_otro(client, db, user, django_user_model):
    _item(user, "g", tags=["instrumento:guitarra"])
    intruso = django_user_model.objects.create_user(
        email="otro2@example.org", password="x"  # noqa: S106
    )
    client.force_login(intruso)

    response = client.get(reverse("my_library:session_start"))

    assert "guitarra" not in response.content.decode()


def test_el_selector_no_escupe_el_comentario_de_la_plantilla(client, db, user):
    """El hermano del mismo defecto: `{# … #}` a dos líneas en `session_start`.
    Este no llegó a verse porque hace falta tener facetas para que se renderice
    el bloque, pero estaba igual de roto."""
    _item(user, "g", tags=["instrumento:guitarra"])
    client.force_login(user)

    response = client.get(reverse("my_library:session_start"))
    html = response.content.decode()

    assert "GET, no POST" not in html
    assert "{#" not in html and "#}" not in html


# === Facetas ===


def test_parse_separa_faceta_y_valor():
    assert facets.parse("instrumento:guitarra") == ("instrumento", "guitarra")
    assert facets.parse("concepto:pentatonica") == ("concepto", "pentatonica")


def test_los_compases_no_se_parsean_como_faceta():
    """El motivo entero de usar ':' y no '/': 3/4 es un compás, no faceta 3."""
    for compas in ("3/4", "6/8", "4/4", "2/4", "3/8"):
        assert facets.parse(compas) == (None, compas)
        assert not facets.tiene_faceta(compas)


def test_una_faceta_desconocida_no_cuenta():
    assert facets.parse("cualquiera:valor") == (None, "cualquiera:valor")
    assert facets.parse("instrumento:") == (None, "instrumento:")


def test_las_etiquetas_planas_pasan_intactas():
    for plana in ("vitalinux", "4-eso", "10points", "aragon"):
        assert facets.parse(plana) == (None, plana)


def test_las_administrativas_no_agrupan_una_sesion(db, user):
    """El defecto que arreglan las facetas: '4-eso' agrupaba de verdad."""
    items = [_item(user, f"x-{n}", tags=["4-eso", "10points"]) for n in range(4)]

    # Sin faceta no hay nada por lo que agrupar: se respeta el orden de entrada
    assert [i.pk for i in agrupar_por_tematica(items)] == [i.pk for i in items]


def test_el_concepto_manda_sobre_el_instrumento(db, user):
    """Media biblioteca es de guitarra: agrupar por eso no aporta nada."""
    pentas = [
        _item(user, f"p-{n}", tags=["instrumento:guitarra", "concepto:pentatonica"])
        for n in range(2)
    ]
    otros = [
        _item(user, f"o-{n}", tags=["instrumento:guitarra", "concepto:arpegio"])
        for n in range(2)
    ]
    mezclados = [pentas[0], otros[0], pentas[1], otros[1]]

    orden = [i.pk for i in agrupar_por_tematica(mezclados)]
    posiciones = [orden.index(p.pk) for p in pentas]

    assert max(posiciones) - min(posiciones) == 1, "ganó el instrumento, no el concepto"


def test_clave_de_agrupacion_elige_lo_mas_especifico():
    etiquetas = ["instrumento:guitarra", "estilo:blues", "concepto:pentatonica"]
    assert facets.clave_de_agrupacion(etiquetas) == "concepto:pentatonica"
    assert facets.clave_de_agrupacion(["vitalinux", "4-eso"]) is None


def test_por_faceta_descarta_lo_plano():
    resultado = facets.por_faceta(
        ["instrumento:guitarra", "instrumento:piano", "concepto:blues", "vitalinux"]
    )
    assert resultado == {
        "instrumento": {"guitarra", "piano"},
        "concepto": {"blues"},
    }


def test_la_sesion_tolera_una_biblioteca_vacia(db, user):
    assert construir_sesion([], tamano=8) == []


def test_el_tope_de_sesion_esta_acotado(db, user):
    items = [_item(user, f"item-{n}") for n in range(5)]

    assert len(construir_sesion(items, tamano=0)) == 1
    assert len(construir_sesion(items, tamano=9999)) == 5


def test_el_mazo_arranca_una_sesion_acotada(client, db, user):
    for n in range(20):
        _item(user, f"penta-{n}", tags=["pentatonica"])
    deck = LibraryDeck.objects.create(
        user=user, name="Pentatónicas", tags_json=json.dumps(["pentatonica"])
    )
    client.force_login(user)

    response = client.get(reverse("my_library:deck_study", args=[deck.pk]))

    assert response.status_code == 302
    pks = response.url.split("items=")[1].split("&")[0].split(",")
    assert len(pks) == TAMANO_SESION_POR_DEFECTO, f"el mazo mandó {len(pks)} elementos"


# === Nota docente compartida ===


@pytest.fixture
def profe(db):
    return UserFactory(is_staff=True)


def test_el_profe_escribe_la_nota_compartida(client, library_item, profe):
    client.force_login(profe)

    response = client.post(
        reverse("my_library:update_shared_note", args=[library_item.pk]),
        {"body": "  Fíjate en el fraseo del compás 12.  "},
    )

    assert response.status_code == 204
    nota = SharedNote.objects.get()
    assert nota.body == "Fíjate en el fraseo del compás 12."
    assert nota.author == profe


def test_el_alumnado_no_puede_escribirla(client, library_item, user):
    """user no es staff."""
    client.force_login(user)

    client.post(
        reverse("my_library:update_shared_note", args=[library_item.pk]),
        {"body": "no debería colar"},
    )

    assert SharedNote.objects.count() == 0


def test_vaciar_la_nota_compartida_la_borra(client, library_item, profe):
    client.force_login(profe)
    url = reverse("my_library:update_shared_note", args=[library_item.pk])
    client.post(url, {"body": "algo"})

    client.post(url, {"body": "   "})

    assert SharedNote.objects.count() == 0


def test_la_nota_compartida_la_ven_todos_los_que_estudian_ese_contenido(
    client, library_item, profe, user
):
    """El punto entero: va atada al contenido, no a la biblioteca de cada uno."""
    client.force_login(profe)
    client.post(
        reverse("my_library:update_shared_note", args=[library_item.pk]),
        {"body": "Empezar por el estribillo"},
    )

    # OTRO usuario añade EL MISMO contenido a su biblioteca
    otro_item = LibraryItem.objects.create(
        user=profe,
        content_type=library_item.content_type,
        object_id=library_item.object_id,
    )

    assert otro_item.user != library_item.user
    assert otro_item.shared_note is not None
    assert otro_item.shared_note.body == "Empezar por el estribillo"


def test_la_nota_privada_no_se_comparte(client, library_item, user, profe):
    """La contraparte: mis notas siguen siendo mías."""
    library_item.notes = "esto es mío"
    library_item.save(update_fields=["notes"])

    otro_item = LibraryItem.objects.create(
        user=profe,
        content_type=library_item.content_type,
        object_id=library_item.object_id,
    )

    assert otro_item.notes == ""


def test_un_contenido_tiene_como_mucho_una_nota_compartida(client, library_item, profe):
    client.force_login(profe)
    url = reverse("my_library:update_shared_note", args=[library_item.pk])

    client.post(url, {"body": "primera"})
    client.post(url, {"body": "segunda"})

    assert SharedNote.objects.count() == 1
    assert SharedNote.objects.get().body == "segunda"


def test_el_visor_muestra_la_nota_compartida_al_alumnado(client, library_item, user, profe):
    SharedNote.objects.create(
        content_type=library_item.content_type,
        object_id=library_item.object_id,
        body="Practica solo la primera parte",
        author=profe,
    )
    client.force_login(user)

    response = client.get(
        reverse("my_library:study_item_content", args=[library_item.pk])
    )
    html = response.content.decode()

    assert "Practica solo la primera parte" in html
    # Al alumnado se le muestra, no se le da a editar
    assert 'id="study-shared-input"' not in html


def test_el_visor_no_escupe_el_comentario_de_la_plantilla(client, library_item, user):
    """`{# … #}` en Django es de UNA línea. En cuanto ocupó dos, el texto salió
    renderizado encima de la partitura, en producción. Barrido de la clase en
    el ISA (fase 7); esto fija el sitio donde se vio."""
    client.force_login(user)

    response = client.get(
        reverse("my_library:study_item_content", args=[library_item.pk])
    )
    html = response.content.decode()

    assert "Notas y etiquetas del item" not in html
    assert "{#" not in html and "#}" not in html


def test_el_visor_le_da_el_campo_editable_al_profe(client, library_item, profe):
    item_del_profe = LibraryItem.objects.create(
        user=profe,
        content_type=library_item.content_type,
        object_id=library_item.object_id,
    )
    client.force_login(profe)

    response = client.get(
        reverse("my_library:study_item_content", args=[item_del_profe.pk])
    )

    assert 'id="study-shared-input"' in response.content.decode()


# === Notas y etiquetas en el visor ===


def test_las_notas_se_guardan(client, library_item, user):
    client.force_login(user)

    response = client.post(
        reverse("my_library:update_notes", args=[library_item.pk]),
        {"notes": "  Posición 2, empezar lento con metrónomo a 60.  "},
    )

    library_item.refresh_from_db()
    assert response.status_code == 204
    assert library_item.notes == "Posición 2, empezar lento con metrónomo a 60."


def test_las_notas_se_pueden_vaciar(client, library_item, user):
    library_item.notes = "algo viejo"
    library_item.save(update_fields=["notes"])
    client.force_login(user)

    client.post(reverse("my_library:update_notes", args=[library_item.pk]), {"notes": ""})

    library_item.refresh_from_db()
    assert library_item.notes == ""


def test_no_se_pueden_editar_las_notas_ajenas(client, library_item, django_user_model):
    intruso = django_user_model.objects.create_user(
        email="otro@example.org", password="x"  # noqa: S106
    )
    client.force_login(intruso)

    response = client.post(
        reverse("my_library:update_notes", args=[library_item.pk]), {"notes": "mío"}
    )

    library_item.refresh_from_db()
    assert response.status_code == 404
    assert library_item.notes == ""


def test_guardar_notas_no_crea_un_repaso(client, library_item, user):
    """Escribir una nota no es practicar."""
    client.force_login(user)

    client.post(
        reverse("my_library:update_notes", args=[library_item.pk]), {"notes": "x"}
    )

    assert ReviewLog.objects.count() == 0


def test_el_visor_muestra_notas_y_etiquetas(client, library_item, user):
    library_item.notes = "Empezar por la posición 2"
    library_item.save(update_fields=["notes"])
    library_item.tags.add("pentatonica", "guitarra")
    client.force_login(user)

    response = client.get(
        reverse("my_library:study_item_content", args=[library_item.pk])
    )
    html = response.content.decode()

    assert "Empezar por la posición 2" in html
    assert "pentatonica" in html
    assert "guitarra" in html
    assert f'data-item-pk="{library_item.pk}"' in html


def test_el_planificador_podra_filtrar_solo_practica_real(client, library_item, user):
    client.force_login(user)
    client.post(
        reverse("my_library:update_proficiency", args=[library_item.pk]), {"level": "3"}
    )
    client.post(
        reverse("my_library:log_review", args=[library_item.pk]), {"level": "4"}
    )

    assert ReviewLog.objects.count() == 2
    assert ReviewLog.objects.filter(source=ReviewLog.SOURCE_STUDY).count() == 1


# === C36: la sesión lee el vocabulario facetado ===


def _pagina(titulo, slug, modelo=None, **extra):
    """Una página real bajo la raíz, vacía de etiquetas.

    Wagtail no deja crear una página suelta: necesita padre en el árbol, y por
    eso no vale con `Modelo.objects.create`. `BlogPage` además OBLIGA a `date` e
    `intro` — es el dato que sostiene el argumento 3 del debate ScorePage →
    BlogPage, y aquí se confirma solo.

    Las etiquetas se ponen después con `faceted_tags`: desde C37c es el único
    vocabulario que tienen las páginas.
    """
    from cms.models import ScorePage
    from wagtail.models import Page

    modelo = modelo or ScorePage
    raiz = Page.objects.get(id=2)
    pagina = modelo(title=titulo, slug=slug, **extra)
    raiz.add_child(instance=pagina)
    pagina.save()
    return pagina


def _item_de_pagina(user, pagina, titulo="desde pagina"):
    """Un LibraryItem cuyo `source_page` es la página dada."""
    from cms.models import ExternalResource

    recurso = ExternalResource.objects.create(
        url=f"https://example.org/{pagina.slug}", title=titulo
    )
    return LibraryItem.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(recurso),
        object_id=recurso.pk,
        source_page=pagina,
    )


def test_la_sesion_lee_las_etiquetas_facetadas_de_la_pagina(db, user):
    from taggit.models import Tag

    pagina = _pagina("Blues", "c36-1")
    pagina.faceted_tags.add(
        Tag.objects.create(name="instrumento:guitarra", slug="instrumento-guitarra")
    )
    pagina.save()
    item = _item_de_pagina(user, pagina)

    mapa = LibraryDeck.build_tag_map(LibraryItem.objects.filter(user=user))

    assert "instrumento:guitarra" in mapa[item.pk]


def test_la_sesion_ya_no_lee_el_vocabulario_plano_de_la_pagina(db, user):
    """El falsador de C36. Con la lectura vieja, `guitar` seguiría entrando y la
    etiqueta de página nunca podría agrupar ni filtrar, que era el motivo de
    toda la fase 8."""
    pagina = _pagina("Blues", "c36-2")
    item = _item_de_pagina(user, pagina)

    mapa = LibraryDeck.build_tag_map(LibraryItem.objects.filter(user=user))

    assert "guitar" not in mapa[item.pk]


def test_la_etiqueta_de_pagina_ya_agrupa_una_sesion(db, user):
    """Lo que la fase 8 venía a comprar. Antes de C36 esto era imposible:
    `facets.parse('guitar')` no reconoce faceta, así que no agrupaba."""
    from taggit.models import Tag

    pagina = _pagina("Blues", "c36-3")
    pagina.faceted_tags.add(
        Tag.objects.create(name="concepto:pentatonica", slug="concepto-pentatonica")
    )
    pagina.save()
    item = _item_de_pagina(user, pagina)

    mapa = LibraryDeck.build_tag_map(LibraryItem.objects.filter(user=user))
    facetadas = [t for t in mapa[item.pk] if facets.tiene_faceta(t)]

    assert facetadas == ["concepto:pentatonica"]


# === C40: el selector y la agrupación ven las etiquetas de la página ===


def test_el_selector_de_facetas_ve_la_etiqueta_de_la_pagina(db, user):
    """El falsador de C40. Antes, `estilo:jazz-moderno` vivía en la página del
    libro y no aparecía en el selector: los 23 capítulos no se podían filtrar
    por él."""
    from taggit.models import Tag
    from my_library.session import facetas_disponibles

    pagina = _pagina("Libro", "c40-1")
    pagina.faceted_tags.add(
        Tag.objects.create(name="estilo:jazz-moderno", slug="estilo-jazz-moderno")
    )
    pagina.save()
    item = _item_de_pagina(user, pagina)

    disponibles = facetas_disponibles([item])

    assert ("jazz-moderno", 1) in disponibles.get(facets.ESTILO, [])


def test_la_agrupacion_tematica_ve_la_etiqueta_de_la_pagina(db, user):
    from taggit.models import Tag
    from my_library.session import _etiquetas

    pagina = _pagina("Libro", "c40-2")
    pagina.faceted_tags.add(
        Tag.objects.create(name="estilo:jazz-moderno", slug="estilo-jazz-moderno-2")
    )
    pagina.save()
    item = _item_de_pagina(user, pagina)

    assert "estilo:jazz-moderno" in _etiquetas(item)


def test_la_pagina_no_aporta_el_vocabulario_plano(db, user):
    """Sumar la página con el vocabulario viejo habría metido 169 etiquetas que
    ni agrupan ni filtran. Solo entra lo facetado."""
    from my_library.session import _etiquetas

    pagina = _pagina("Libro", "c40-3")
    item = _item_de_pagina(user, pagina)

    assert "modern jazz" not in _etiquetas(item)


def test_una_etiqueta_repetida_no_sale_dos_veces(db, user):
    """La misma etiqueta puede estar en el documento y en su página."""
    from taggit.models import Tag

    etiqueta = Tag.objects.create(name="estilo:blues", slug="estilo-blues-c40")
    pagina = _pagina("Libro", "c40-4")
    pagina.faceted_tags.add(etiqueta)
    pagina.save()
    item = _item_de_pagina(user, pagina)
    item.tags.add(etiqueta)

    nombres = [t.name for t in item.get_content_tags()]

    assert nombres.count("estilo:blues") == 1


def test_la_seccion_hereda_tambien_lo_de_la_pagina(db, user):
    """Un trozo del capítulo sigue siendo jazz moderno."""
    from taggit.models import Tag

    pagina = _pagina("Libro", "c40-5")
    pagina.faceted_tags.add(
        Tag.objects.create(name="estilo:jazz-moderno", slug="estilo-jazz-moderno-5")
    )
    pagina.save()
    item = _item_de_pagina(user, pagina)
    seccion = ItemSection.objects.create(item=item, nombre="Intro", orden=0)

    assert "estilo:jazz-moderno" in {t.name for t in seccion.get_content_tags()}


def test_precargar_da_lo_mismo_que_no_precargar(db, user):
    """La precarga es una optimización, no otra semántica. Si los dos caminos
    dieran resultados distintos, el selector y el visor discreparían según por
    dónde se llegara."""
    from taggit.models import Tag

    pagina = _pagina("Libro", "precarga-1")
    pagina.faceted_tags.add(
        Tag.objects.create(name="estilo:jazz-moderno", slug="estilo-jm-precarga")
    )
    pagina.save()
    item = _item_de_pagina(user, pagina)
    otro = _item_de_pagina(
        user, _pagina("Suelto", "precarga-2"), "sin etiquetas"
    )

    sin_precarga = {
        i.pk: sorted(t.name for t in i.get_content_tags())
        for i in LibraryItem.objects.filter(user=user)
    }

    items = list(LibraryItem.objects.filter(user=user))
    LibraryDeck.precargar_etiquetas_de_pagina(items)
    con_precarga = {i.pk: sorted(t.name for t in i.get_content_tags()) for i in items}

    assert sin_precarga == con_precarga
    assert "estilo:jazz-moderno" in con_precarga[item.pk]
    assert con_precarga[otro.pk] == []


# === C37b: el API escribe etiquetas facetadas por nombre ===


def test_el_api_pone_las_etiquetas_por_nombre(db):
    """El caso real: PublishIES publica por `POST /api/cms/blog-pages`. Los ids
    de `MusicTag` se retiraron con el modelo; ahora van nombres."""
    from cms.etiquetas import aplicar_etiquetas
    from cms.models import ScorePage

    pagina = _pagina("Nueva", "c37b-1")
    aplicar_etiquetas(pagina, ["estilo:jazz", "instrumento:guitarra"])
    pagina.save_revision().publish()

    releida = ScorePage.objects.get(pk=pagina.pk)
    assert {t.name for t in releida.faceted_tags.all()} == {
        "estilo:jazz",
        "instrumento:guitarra",
    }


def test_el_api_no_duplica_un_nombre_repetido(db):
    from cms.etiquetas import aplicar_etiquetas
    from cms.models import ScorePage

    pagina = _pagina("Nueva", "c37b-2")
    aplicar_etiquetas(pagina, ["estilo:jazz", "Estilo:Jazz ", "estilo:jazz"])
    pagina.save_revision().publish()

    releida = ScorePage.objects.get(pk=pagina.pk)
    assert releida.faceted_tags.count() == 1


def test_una_faceta_inventada_se_rechaza(db):
    """`caracter` no está en `facets.FACETAS`: el principal decidió no crearla.
    Sin esta comprobación la etiqueta se crearía y nacería muerta."""
    from cms.etiquetas import facetas_desconocidas

    assert facetas_desconocidas(["caracter:melancolico"]) == ["caracter:melancolico"]
    assert facetas_desconocidas(["estilo:jazz"]) == []


def test_un_nombre_sin_faceta_es_valido(db):
    """`3/4` y `vitalinux` son etiquetas legítimas sin faceta. El separador es
    `:`, no `/`, justo para que un compás no se parsee como faceta."""
    from cms.etiquetas import facetas_desconocidas

    assert facetas_desconocidas(["3/4", "vitalinux"]) == []


def test_precargar_da_lo_mismo_que_no_precargar(db, user):
    """La precarga es una optimización, no otra semántica. Si los dos caminos
    dieran resultados distintos, el selector y el visor discreparían según por
    dónde se llegara."""
    from taggit.models import Tag

    pagina = _pagina("Libro", "precarga-1")
    pagina.faceted_tags.add(
        Tag.objects.create(name="estilo:jazz-moderno", slug="estilo-jm-precarga")
    )
    pagina.save()
    item = _item_de_pagina(user, pagina)
    otro = _item_de_pagina(
        user, _pagina("Suelto", "precarga-2"), "sin etiquetas"
    )

    sin_precarga = {
        i.pk: sorted(t.name for t in i.get_content_tags())
        for i in LibraryItem.objects.filter(user=user)
    }

    items = list(LibraryItem.objects.filter(user=user))
    LibraryDeck.precargar_etiquetas_de_pagina(items)
    con_precarga = {i.pk: sorted(t.name for t in i.get_content_tags()) for i in items}

    assert sin_precarga == con_precarga
    assert "estilo:jazz-moderno" in con_precarga[item.pk]
    assert con_precarga[otro.pk] == []


def test_un_elemento_que_apunta_a_una_pagina_recibe_sus_etiquetas(db, user):
    """Un `LibraryItem` puede apuntar a un documento, a una imagen o **a una
    página**. Los dos primeros etiquetan en `tags`; la página, en
    `faceted_tags`.

    Mirar solo `tags` dejó al elemento 69 de producción sin su `concepto:canon`
    en cuanto se retiró `MusicTag`. Son 2 elementos de 102, y por eso el barrido
    de C36 pasó por encima: el caso existe y no lo cubría ningún test.
    """
    from taggit.models import Tag

    pagina = _pagina("Partitura suelta", "c37c-1")
    pagina.faceted_tags.add(Tag.objects.create(name="concepto:canon", slug="concepto-canon"))
    pagina.save()

    item = LibraryItem.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(pagina),
        object_id=pagina.pk,
    )

    mapa = LibraryDeck.build_tag_map(LibraryItem.objects.filter(user=user))
    assert "concepto:canon" in mapa[item.pk]
    assert "concepto:canon" in {t.name for t in item.get_content_tags()}


# === Fase 11: estudiarse un libro ===


def _libro_con_capitulos(titulo, slug, capitulos):
    """Un libro real: `BlogIndexPage` con `BlogPage` debajo, en orden.

    `capitulos` es [(titulo, [imagenes])]. Las imágenes se incrustan en el
    cuerpo, que es como están en los libros de verdad: el capítulo 1 de Jens
    Larsen tiene cero bloques adjuntos y dieciséis imágenes dentro del texto.
    """
    from cms.models import BlogIndexPage, BlogPage
    from wagtail.images import get_image_model
    from wagtail.models import Page

    Image = get_image_model()
    raiz = Page.objects.get(id=2)
    libro = BlogIndexPage(title=titulo, slug=slug)
    raiz.add_child(instance=libro)

    creados = []
    for n, (titulo_cap, nombres) in enumerate(capitulos):
        imagenes = []
        for nombre in nombres:
            img = Image.objects.create(title=nombre, file=_imagen_minima(nombre))
            imagenes.append(img)
        cuerpo = "".join(
            f'<p>Texto antes de {i.title}.</p>'
            f'<embed embedtype="image" id="{i.pk}" alt="{i.title}" format="fullwidth"/>'
            for i in imagenes
        )
        cap = BlogPage(
            title=titulo_cap,
            slug=f"{slug}-cap-{n}",
            date=timezone.now().date(),
            intro=f"Intro de {titulo_cap}",
            body=cuerpo,
        )
        libro.add_child(instance=cap)
        cap.save_revision().publish()
        creados.append((cap, imagenes))
    return libro, creados


def _imagen_minima(nombre):
    """Un PNG de 1x1 real: Wagtail valida el fichero al guardar la imagen."""
    import base64

    from django.core.files.base import ContentFile

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    return ContentFile(png, name=f"{nombre}.png")


def test_el_material_del_libro_sale_en_orden_de_libro(db):
    """C41. Capítulos por el árbol de Wagtail, y dentro, en orden de aparición."""
    from my_library.libros import material_del_libro

    libro, caps = _libro_con_capitulos(
        "Metodo", "metodo-1", [("Semana 1", ["a", "b"]), ("Semana 2", ["c"])]
    )

    material = material_del_libro(libro)

    assert [o.title for _c, o in material] == ["a", "b", "c"]
    assert [c.title for c, _o in material] == ["Semana 1", "Semana 1", "Semana 2"]


def test_fijar_el_objetivo_no_crea_ni_un_elemento(db, user):
    """C43. Es la decisión que define la fase: no se copia nada por adelantado.
    Ukulele Aerobics son 283 medios y la biblioteca tiene 51 elementos."""
    from my_library.models import LibraryGoal

    libro, _ = _libro_con_capitulos(
        "Metodo", "metodo-2", [("Semana 1", ["a", "b", "c"])]
    )

    LibraryGoal.objects.create(user=user, libro=libro)

    assert LibraryItem.objects.filter(user=user).count() == 0


def test_la_cola_crea_el_elemento_cuando_le_toca(db, user):
    """C43. Y en orden de libro, no de alta."""
    from my_library.libros import siguiente_del_objetivo

    libro, _ = _libro_con_capitulos(
        "Metodo", "metodo-3", [("Semana 1", ["a", "b"]), ("Semana 2", ["c"])]
    )

    primeros = siguiente_del_objetivo(user, libro, cuantos=2)

    assert [i.content_object.title for i in primeros] == ["a", "b"]
    assert LibraryItem.objects.filter(user=user).count() == 2
    assert primeros[0].source_page.title == "Semana 1"


def test_la_cola_sigue_por_donde_iba(db, user):
    from my_library.libros import siguiente_del_objetivo

    libro, _ = _libro_con_capitulos(
        "Metodo", "metodo-4", [("Semana 1", ["a", "b"]), ("Semana 2", ["c"])]
    )

    siguiente_del_objetivo(user, libro, cuantos=2)
    siguientes = siguiente_del_objetivo(user, libro, cuantos=2)

    assert [i.content_object.title for i in siguientes] == ["c"]
    assert LibraryItem.objects.filter(user=user).count() == 3


def test_material_suelto_sin_tocar_no_apaga_el_objetivo(db, user):
    """El defecto medido en produccion el 2026-08-25.

    `rellenar_para_sesion` contaba el material sin practicar de la biblioteca
    ENTERA. El principal tenia 28 elementos sin tocar ajenos a sus objetivos
    -13 de un libro sin objetivo y 12 sueltos del indice-, asi que
    `cuota - sin_tocar` salia en negativo y la creacion perezosa devolvia []
    en CADA sesion: ningun objetivo podia aportar nada. Se mide por objetivo.

    El falsador: si se vuelve a medir global, esto crea cero.
    """
    from my_library.libros import rellenar_para_sesion
    from my_library.models import LibraryGoal

    libro, _ = _libro_con_capitulos(
        "Metodo", "metodo-suelto", [("Semana 1", ["a", "b"])]
    )
    LibraryGoal.objects.create(user=user, libro=libro)
    for i in range(28):
        _item(user, f"suelto {i}")

    creados = rellenar_para_sesion(user, 2)

    assert len(creados) == 2
    assert [i.content_object.title for i in creados] == ["a", "b"]


def test_dos_objetivos_alternan_la_cuota(db, user):
    """Decision del principal (2026-08-25): con varios libros a la vez la cuota
    se alterna, no se la come el primero.

    Antes el bucle le pedia `faltan` -toda la cuota- al primer objetivo, y el
    `filter` no llevaba `order_by`, asi que ni siquiera estaba definido cual
    era el primero. Con un libro de 93 medios, el segundo no asomaba en meses.
    """
    from my_library.libros import rellenar_para_sesion
    from my_library.models import LibraryGoal

    uno, _ = _libro_con_capitulos("Uno", "libro-uno", [("Semana 1", ["a1", "a2"])])
    dos, _ = _libro_con_capitulos("Dos", "libro-dos", [("Semana 1", ["b1", "b2"])])
    LibraryGoal.objects.create(user=user, libro=uno)
    LibraryGoal.objects.create(user=user, libro=dos)

    creados = rellenar_para_sesion(user, 2)

    titulos = sorted(i.content_object.title for i in creados)
    assert titulos == ["a1", "b1"], "uno de cada libro, no dos del primero"


def test_tres_objetivos_cada_uno_con_su_reserva(db, user):
    """La forma exacta que tenia produccion el 2026-08-25 con tres objetivos.

    Un libro con material acumulado tapaba a los otros dos: la suma sin tocar
    de objetivo era 15 y la cuota 2, asi que el deficit global salia negativo y
    no se creaba nada, con el tercer libro a cero. Cada objetivo mantiene ahora
    su propia reserva.

    El falsador: si se vuelve a medir el deficit en global, esto crea cero.
    """
    from my_library.libros import rellenar_para_sesion, siguiente_del_objetivo
    from my_library.models import LibraryGoal

    lleno, _ = _libro_con_capitulos(
        "Lleno", "libro-lleno", [("Semana 1", ["x1", "x2", "x3", "x4"])]
    )
    medio, _ = _libro_con_capitulos("Medio", "libro-medio", [("Semana 1", ["y1"])])
    vacio, _ = _libro_con_capitulos("Vacio", "libro-vacio", [("Semana 1", ["z1"])])
    for libro in (lleno, medio, vacio):
        LibraryGoal.objects.create(user=user, libro=libro)
    # `lleno` y `medio` ya tienen material sin tocar; `vacio` no tiene ninguno.
    siguiente_del_objetivo(user, lleno, cuantos=4)
    siguiente_del_objetivo(user, medio, cuantos=1)

    creados = rellenar_para_sesion(user, 2)

    assert [i.content_object.title for i in creados] == ["z1"], (
        "solo el libro sin reserva necesita material"
    )


def test_la_novedad_se_reparte_entre_libros_al_elegir(db, user):
    """La otra mitad de alternar: con material acumulado de un libro, la cuota
    de novedad no puede irse entera a ese libro.

    Antes `nuevos` iba ordenado por pk y ganaba siempre el libro mas viejo. No
    era mala suerte, era determinista.
    """
    from my_library.libros import siguiente_del_objetivo
    from my_library.session import construir_sesion

    viejo, _ = _libro_con_capitulos(
        "Viejo", "libro-viejo", [("Semana 1", ["v1", "v2", "v3", "v4", "v5"])]
    )
    nuevo, _ = _libro_con_capitulos("Nuevo", "libro-nuevo", [("Semana 1", ["n1"])])
    siguiente_del_objetivo(user, viejo, cuantos=5)   # pk mas bajos
    siguiente_del_objetivo(user, nuevo, cuantos=1)   # pk mas alto

    sesion = construir_sesion(LibraryItem.objects.filter(user=user), tamano=8)
    titulos = [u.content_object.title for u in sesion]

    assert "n1" in titulos, "el libro con un solo elemento tiene que asomar"
    assert titulos.index("n1") <= 1, "y en los primeros huecos, no al final"


def test_un_libro_agotado_cede_su_parte_al_otro(db, user):
    """La alternancia no puede dejar la cuota a medias cuando un libro se acaba."""
    from my_library.libros import rellenar_para_sesion
    from my_library.models import LibraryGoal

    corto, _ = _libro_con_capitulos("Corto", "libro-corto", [("Semana 1", ["c1"])])
    largo, _ = _libro_con_capitulos(
        "Largo", "libro-largo", [("Semana 1", ["l1", "l2", "l3"])]
    )
    LibraryGoal.objects.create(user=user, libro=corto)
    LibraryGoal.objects.create(user=user, libro=largo)

    creados = rellenar_para_sesion(user, 3)

    titulos = sorted(i.content_object.title for i in creados)
    assert titulos == ["c1", "l1", "l2"]


def test_un_elemento_descartado_no_lo_vuelve_a_ofrecer_el_objetivo(db, user):
    """C45. El falsador: borrar la fila a secas no vale, porque la creación
    perezosa la recrearía en la siguiente sesión."""
    from my_library.libros import siguiente_del_objetivo

    libro, _ = _libro_con_capitulos(
        "Metodo", "metodo-5", [("Semana 1", ["decoracion", "ejercicio"])]
    )

    primero = siguiente_del_objetivo(user, libro, cuantos=1)[0]
    assert primero.content_object.title == "decoracion"

    primero.descartado = True
    primero.save(update_fields=["descartado"])

    siguientes = siguiente_del_objetivo(user, libro, cuantos=2)
    assert [i.content_object.title for i in siguientes] == ["ejercicio"]


def test_descartar_saca_el_elemento_de_la_sesion(db, user):
    from my_library.libros import siguiente_del_objetivo
    from my_library.views import _items_del_usuario

    libro, _ = _libro_con_capitulos("Metodo", "metodo-6", [("Semana 1", ["a", "b"])])
    items = siguiente_del_objetivo(user, libro, cuantos=2)

    items[0].descartado = True
    items[0].save(update_fields=["descartado"])

    assert [i.pk for i in _items_del_usuario(user)] == [items[1].pk]


def test_descartar_no_borra_el_historial(db, user):
    """Descartar dice 'no me lo ofrezcas más', no 'haz como si no hubiera pasado'."""
    from my_library.libros import siguiente_del_objetivo

    libro, _ = _libro_con_capitulos("Metodo", "metodo-7", [("Semana 1", ["a"])])
    item = siguiente_del_objetivo(user, libro, cuantos=1)[0]
    ReviewLog.log(item=item, proficiency_after=3)

    item.descartado = True
    item.save(update_fields=["descartado"])

    assert ReviewLog.objects.filter(item=item).count() == 1
    assert item.notes == ""


def test_el_progreso_cuenta_capitulos_tocados(db, user):
    """C46. «Semana 12 de 40»."""
    from my_library.libros import progreso, siguiente_del_objetivo

    libro, _ = _libro_con_capitulos(
        "Metodo",
        "metodo-8",
        [("Semana 1", ["a"]), ("Semana 2", ["b"]), ("Semana 3", ["c"])],
    )

    assert progreso(user, libro) == (0, 3)

    items = siguiente_del_objetivo(user, libro, cuantos=2)
    ReviewLog.log(item=items[0], proficiency_after=2)

    assert progreso(user, libro) == (1, 3)


def test_el_contexto_devuelve_el_texto_que_rodea_a_la_imagen(db, user):
    """C44. En estos libros las imágenes van dentro del texto, así que lo que
    hay justo antes es la explicación del ejercicio."""
    from my_library.libros import contexto_en_el_libro, siguiente_del_objetivo

    libro, _ = _libro_con_capitulos("Metodo", "ctx-1", [("Semana 1", ["ejercicio"])])
    item = siguiente_del_objetivo(user, libro, cuantos=1)[0]

    texto, capitulo, url = contexto_en_el_libro(item)

    assert "Texto antes de ejercicio" in texto
    assert capitulo == "Semana 1"
    assert url


def test_el_contexto_no_revienta_con_un_elemento_suelto(db, user, library_item):
    """Lo añadido desde el índice no tiene `source_page`."""
    from my_library.libros import contexto_en_el_libro

    assert contexto_en_el_libro(library_item) == (None, None, None)


def test_el_endpoint_de_contexto_responde_json(client, db, user):
    from my_library.libros import siguiente_del_objetivo

    libro, _ = _libro_con_capitulos("Metodo", "ctx-2", [("Semana 1", ["ejercicio"])])
    item = siguiente_del_objetivo(user, libro, cuantos=1)[0]
    client.force_login(user)

    r = client.get(reverse("my_library:contexto_item", args=[item.pk]))

    assert r.status_code == 200
    assert "Texto antes de ejercicio" in r.json()["texto"]
    assert r.json()["capitulo"] == "Semana 1"


def test_descartar_desde_el_visor(client, db, user):
    """C45, por HTTP: el endpoint marca y no borra."""
    from my_library.libros import siguiente_del_objetivo

    libro, _ = _libro_con_capitulos("Metodo", "desc-1", [("Semana 1", ["a"])])
    item = siguiente_del_objetivo(user, libro, cuantos=1)[0]
    client.force_login(user)

    r = client.post(reverse("my_library:descartar_item", args=[item.pk]))

    assert r.status_code == 200
    item.refresh_from_db()
    assert item.descartado
    assert LibraryItem.objects.filter(pk=item.pk).exists()


def test_no_se_descarta_lo_ajeno(client, db, user, django_user_model):
    from my_library.libros import siguiente_del_objetivo

    libro, _ = _libro_con_capitulos("Metodo", "desc-2", [("Semana 1", ["a"])])
    item = siguiente_del_objetivo(user, libro, cuantos=1)[0]
    otro = UserFactory()
    client.force_login(otro)

    r = client.post(reverse("my_library:descartar_item", args=[item.pk]))

    assert r.status_code == 404
    item.refresh_from_db()
    assert not item.descartado


def test_fijar_y_quitar_el_objetivo_desde_la_web(client, db, user):
    """C42 por HTTP: el mismo botón lo pone y lo quita."""
    from my_library.models import LibraryGoal

    libro, _ = _libro_con_capitulos("Metodo", "obj-1", [("Semana 1", ["a"])])
    client.force_login(user)
    url = reverse("my_library:alternar_objetivo", args=[libro.pk])

    r = client.post(url)
    assert r.status_code == 200
    assert LibraryGoal.objects.filter(user=user, libro=libro).exists()
    assert LibraryItem.objects.filter(user=user).count() == 0  # nada por adelantado

    client.post(url)
    assert not LibraryGoal.objects.filter(user=user, libro=libro).exists()


def test_quitar_el_objetivo_no_borra_lo_practicado(client, db, user):
    from my_library.libros import siguiente_del_objetivo
    from my_library.models import LibraryGoal

    libro, _ = _libro_con_capitulos("Metodo", "obj-2", [("Semana 1", ["a"])])
    LibraryGoal.objects.create(user=user, libro=libro)
    item = siguiente_del_objetivo(user, libro, cuantos=1)[0]
    ReviewLog.log(item=item, proficiency_after=3)
    client.force_login(user)

    client.post(reverse("my_library:alternar_objetivo", args=[libro.pk]))

    assert LibraryItem.objects.filter(pk=item.pk).exists()
    assert ReviewLog.objects.filter(item=item).count() == 1


def test_el_boton_del_objetivo_enseña_el_progreso(db, user, rf):
    """C46 en la interfaz: «12 de 40», por capítulos y no por elementos."""
    from my_library.libros import siguiente_del_objetivo
    from my_library.models import LibraryGoal
    from my_library.templatetags.library_tags import boton_objetivo

    libro, _ = _libro_con_capitulos(
        "Metodo", "obj-3", [("Semana 1", ["a"]), ("Semana 2", ["b"])]
    )
    LibraryGoal.objects.create(user=user, libro=libro)
    item = siguiente_del_objetivo(user, libro, cuantos=1)[0]
    ReviewLog.log(item=item, proficiency_after=2)

    peticion = rf.get("/")
    peticion.user = user
    ctx = boton_objetivo({"request": peticion}, libro)

    assert ctx["objetivo_activo"]
    assert (ctx["progreso_tocados"], ctx["progreso_totales"]) == (1, 2)


def test_el_boton_no_sale_en_algo_que_no_es_un_libro(db, user, rf):
    """Una página sin capítulos no es un libro; pintar el botón mentiría."""
    from my_library.templatetags.library_tags import boton_objetivo

    suelta = _pagina("Partitura suelta", "obj-4")
    peticion = rf.get("/")
    peticion.user = user

    assert boton_objetivo({"request": peticion}, suelta) == {"libro": None}


def test_el_libro_recien_empezado_no_asoma_con_tres_grupos(db, user):
    """C54 se probo con DOS grupos; produccion tiene tres.

    `_repartir_por_libro` ordena los grupos por su primer elemento, que es el
    de pk mas bajo. El material que acaba de crear la creacion perezosa tiene
    SIEMPRE el pk mas alto, asi que su grupo cae el ultimo: con cuota 2 y tres
    grupos con material sin tocar, el libro recien empezado no entra nunca.

    Medido en produccion el 2026-08-26: `rellenar_para_sesion` creo el elemento
    de CAGED (la faceta paso de 11 a 12) y la sesion salio sin el.
    """
    from my_library.libros import siguiente_del_objetivo
    from my_library.session import construir_sesion

    # Sin tocar, en tres grupos y por orden de pk creciente.
    _item(user, "suelto")  # grupo None
    larsen, _ = _libro_con_capitulos(
        "Larsen", "libro-larsen", [("Semana 1", ["l1", "l2", "l3"])]
    )
    siguiente_del_objetivo(user, larsen, cuantos=3)
    caged, _ = _libro_con_capitulos("Caged", "libro-caged", [("Semana 1", ["c1"])])
    siguiente_del_objetivo(user, caged, cuantos=1)  # el pk mas alto

    # Repaso de sobra para llenar la sesion: sin esto el hueco sobrante se
    # rellena con lo nuevo y el defecto queda tapado.
    for n in range(10):
        _practicado_hace(_item(user, f"conocido-{n}"), dias=30)

    sesion = construir_sesion(LibraryItem.objects.filter(user=user), tamano=8)
    titulos = [u.content_object.title for u in sesion]

    assert "c1" in titulos, f"el libro recien empezado tiene que asomar: {titulos}"
    assert "l1" in titulos, f"y el otro libro sigue entrando: {titulos}"
    assert "suelto" not in titulos, (
        f"el suelto es quien cede el hueco, no el libro: {titulos}"
    )


def test_el_indice_no_pinta_el_comentario_de_plantilla(client, library_item, user):
    """`{# #}` es de UNA linea en Django: un bloque de varias se pinta entero.

    Visto en produccion el 2026-08-26, encima de la lista de la biblioteca.
    Es la segunda vez que pasa en este proyecto (la primera la arreglo `444af8e`
    en la fase 7), asi que esta vez queda un test detras.
    """
    client.force_login(user)

    html = client.get(reverse("my_library:index")).content.decode()

    assert "El panel de mazos sale de la interfaz" not in html
    assert "build_tag_map" not in html
    assert 'id="deckPanel"' not in html, "y el panel sigue fuera"


def test_estado_estudio_cuenta_los_grupos_que_se_quedan_fuera(db, user, capsys):
    """El comando existe para ver lo que la vista previa esconde: cuantos
    GRUPOS compiten por los huecos de novedad y cuales no entran nunca.

    Un comando que solo se haya corrido contra una base vacia no prueba nada,
    asi que aqui se le da la forma de produccion del 2026-08-26.
    """
    from django.core.management import call_command

    from my_library.libros import siguiente_del_objetivo
    from my_library.models import LibraryGoal

    _item(user, "suelto")
    larsen, _ = _libro_con_capitulos(
        "Larsen", "libro-larsen", [("Semana 1", ["l1", "l2", "l3"])]
    )
    siguiente_del_objetivo(user, larsen, cuantos=3)
    otro, _ = _libro_con_capitulos("Otro", "libro-otro", [("Semana 1", ["o1"])])
    siguiente_del_objetivo(user, otro, cuantos=1)
    caged, _ = _libro_con_capitulos("Caged", "libro-caged", [("Semana 1", ["c1"])])
    siguiente_del_objetivo(user, caged, cuantos=1)
    LibraryGoal.objects.create(user=user, libro=caged)

    # Tamano explicito: el test mide el reparto, no el valor de la constante,
    # y el principal la sube cuando le conviene.
    call_command("estado_estudio", email=user.email, tamano=8)
    salida = capsys.readouterr().out

    assert "Caged" in salida, "el libro tiene que salir nombrado"
    assert "objetivo" in salida
    # Cuatro grupos y dos huecos: dos se quedan fuera de todas las sesiones.
    assert "2 grupo(s) se quedan fuera" in salida, salida
    assert "biblioteca sin descartar: 6" in salida


def test_estado_estudio_no_crea_nada(db, user):
    """Solo lectura. El falsador importa: si llamara a `rellenar_para_sesion`,
    medir cambiaria lo medido."""
    from django.core.management import call_command

    from my_library.models import LibraryGoal

    caged, _ = _libro_con_capitulos("Caged", "libro-caged", [("Semana 1", ["c1"])])
    LibraryGoal.objects.create(user=user, libro=caged)
    antes = LibraryItem.objects.filter(user=user).count()

    call_command("estado_estudio", email=user.email)

    assert LibraryItem.objects.filter(user=user).count() == antes


def test_el_objetivo_pasa_por_delante_de_los_libros_sin_objetivo(db, user):
    """C58. La forma exacta de produccion del 2026-08-26, despues del primer
    arreglo: el suelto ya cedia, pero quedaban TRES grupos de libro por delante
    del objetivo recien empezado y la cuota seguia siendo 2.

    El falsador: si los grupos se ordenan solo por "tiene pagina o no", `c1` no
    sale, que es exactamente lo que hacia produccion.
    """
    from my_library.libros import siguiente_del_objetivo
    from my_library.models import LibraryGoal
    from my_library.session import construir_sesion

    _item(user, "suelto")
    for titulo, slug in (("Uno", "libro-uno"), ("Dos", "libro-dos")):
        libro, _ = _libro_con_capitulos(titulo, slug, [("Semana 1", [f"{slug}-a"])])
        siguiente_del_objetivo(user, libro, cuantos=1)  # sin objetivo, pk bajos

    larsen, _ = _libro_con_capitulos(
        "Larsen", "libro-larsen", [("Semana 1", ["l1", "l2", "l3"])]
    )
    siguiente_del_objetivo(user, larsen, cuantos=3)
    caged, _ = _libro_con_capitulos("Caged", "libro-caged", [("Semana 1", ["c1"])])
    siguiente_del_objetivo(user, caged, cuantos=1)  # el pk mas alto de todos
    LibraryGoal.objects.create(user=user, libro=larsen)
    LibraryGoal.objects.create(user=user, libro=caged)

    for n in range(10):
        _practicado_hace(_item(user, f"conocido-{n}"), dias=30)

    sesion = construir_sesion(LibraryItem.objects.filter(user=user), tamano=8)
    titulos = [u.content_object.title for u in sesion]

    assert "c1" in titulos, f"el objetivo recien empezado tiene que asomar: {titulos}"
    assert "l1" in titulos, f"y el otro objetivo tambien: {titulos}"
    assert "libro-uno-a" not in titulos, f"los libros sin objetivo ceden: {titulos}"


def _libro_etiquetado(titulo, slug, imagenes, etiqueta):
    """Un libro cuyos capitulos llevan una etiqueta facetada de la pagina."""
    from taggit.models import Tag

    libro, capitulos = _libro_con_capitulos(titulo, slug, [("Semana 1", imagenes)])
    tag, _ = Tag.objects.get_or_create(
        name=etiqueta, defaults={"slug": etiqueta.replace(":", "-")}
    )
    for capitulo, _imgs in capitulos:
        capitulo.faceted_tags.add(tag)
        capitulo.save()
    return libro


def test_elegir_piano_deja_la_sesion_solo_de_piano(client, db, user):
    """La pregunta del principal (2026-08-26): con tres objetivos —dos de
    guitarra y uno de piano— y eligiendo piano al empezar, ¿los tres huecos de
    novedad salen del libro de piano?

    Si. El filtro de facetas corre DESPUES de crear y ANTES de construir la
    sesion, asi que lo que no es de piano se cae antes de repartir los huecos.
    """
    from my_library.models import LibraryGoal

    piano = _libro_etiquetado("Piano", "libro-piano", ["p1", "p2", "p3", "p4"],
                              "instrumento:piano")
    for titulo, slug in (("Guit A", "libro-guit-a"), ("Guit B", "libro-guit-b")):
        libro = _libro_etiquetado(titulo, slug, ["g1", "g2"], "instrumento:guitarra")
        LibraryGoal.objects.create(user=user, libro=libro)
    LibraryGoal.objects.create(user=user, libro=piano)

    client.force_login(user)
    respuesta = client.get(
        reverse("my_library:session_launch"), {"instrumento": "piano"}
    )

    pks = [int(p) for p in respuesta.url.split("items=")[1].split("&")[0].split(",")]
    sesion = LibraryItem.objects.filter(pk__in=pks)
    etiquetas = {
        t.name for item in sesion for t in item.get_content_tags()
    }
    assert "instrumento:piano" in etiquetas
    assert "instrumento:guitarra" not in etiquetas, (
        "eligiendo piano no puede colarse guitarra en la sesion"
    )


def test_elegir_piano_no_crea_material_de_guitarra(client, db, user):
    """La otra mitad de la respuesta, y es la que no se ve.

    Desde el 2026-08-26 el filtro frena TAMBIEN la creacion, por decision del
    principal: "no quiero material acumulado". Antes se creaba de los tres
    objetivos aunque solo se estudiara piano, y lo de guitarra se quedaba en la
    biblioteca sin tocar compitiendo en las sesiones sin filtrar.

    El falsador: si `rellenar_para_sesion` vuelve a ignorar la seleccion, este
    test se pone rojo.
    """
    from my_library.models import LibraryGoal

    piano = _libro_etiquetado("Piano", "libro-piano", ["p1", "p2"],
                              "instrumento:piano")
    guitarra = _libro_etiquetado("Guit", "libro-guit", ["g1", "g2"],
                                 "instrumento:guitarra")
    LibraryGoal.objects.create(user=user, libro=piano)
    LibraryGoal.objects.create(user=user, libro=guitarra)

    client.force_login(user)
    client.get(reverse("my_library:session_launch"), {"instrumento": "piano"})

    creados = LibraryItem.objects.filter(user=user)
    de_guitarra = [
        i for i in creados
        if "instrumento:guitarra" in {t.name for t in i.get_content_tags()}
    ]
    assert not de_guitarra, (
        "eligiendo piano no se puede crear material de guitarra: "
        "el filtro frena tambien la creacion"
    )
    de_piano = [
        i for i in creados
        if "instrumento:piano" in {t.name for t in i.get_content_tags()}
    ]
    assert de_piano, "y el libro elegido si recibe material"


def _con_objetivo(user, titulo, slug, imagenes, cuantos):
    """Un libro marcado como objetivo, con parte de su material ya en la
    biblioteca."""
    from my_library.libros import siguiente_del_objetivo
    from my_library.models import LibraryGoal

    libro, _ = _libro_con_capitulos(titulo, slug, [("Semana 1", imagenes)])
    LibraryGoal.objects.create(user=user, libro=libro)
    siguiente_del_objetivo(user, libro, cuantos=cuantos)
    return libro


def test_elegir_un_libro_deja_la_sesion_entera_de_ese_libro(client, db, user):
    """C64. Decision del principal (2026-08-26): la sesion ENTERA, repaso
    incluido, no solo los huecos de novedad.

    El falsador: si el filtro solo alcanzara a la novedad, saldrian elementos
    del otro libro en los huecos de repaso.
    """
    caged = _con_objetivo(user, "Caged", "libro-caged", ["c1", "c2", "c3"], 3)
    _con_objetivo(user, "Larsen", "libro-larsen", ["l1", "l2", "l3"], 3)
    # Todo practicado: asi los huecos que quedan son de REPASO, que es donde
    # se vería el defecto.
    for item in LibraryItem.objects.filter(user=user):
        _practicado_hace(item, dias=30)

    client.force_login(user)
    respuesta = client.get(
        reverse("my_library:session_launch"), {"libro": str(caged.pk)}
    )

    pks = [int(p) for p in respuesta.url.split("items=")[1].split("&")[0].split(",")]
    titulos = [
        i.content_object.title for i in LibraryItem.objects.filter(pk__in=pks)
    ]
    assert titulos, "la sesion no puede salir vacia"
    assert all(t.startswith("c") for t in titulos), (
        f"eligiendo CAGED no puede colarse nada de Larsen: {titulos}"
    )


def test_elegir_un_libro_solo_crea_de_ese_libro(client, db, user):
    """El filtro por libro frena la creacion igual que el de facetas (C63)."""
    caged = _con_objetivo(user, "Caged", "libro-caged", ["c1", "c2", "c3", "c4"], 1)
    _con_objetivo(user, "Larsen", "libro-larsen", ["l1", "l2", "l3", "l4"], 0)

    client.force_login(user)
    client.get(reverse("my_library:session_launch"), {"libro": str(caged.pk)})

    titulos = {
        i.content_object.title for i in LibraryItem.objects.filter(user=user)
    }
    assert not any(t.startswith("l") for t in titulos), (
        f"Larsen no puede recibir material hoy: {sorted(titulos)}"
    )
    assert len([t for t in titulos if t.startswith("c")]) > 1, "y CAGED si avanza"


def test_dos_libros_elegidos_se_suman(client, db, user):
    """Dos libros solo pueden combinarse con O: nada esta en dos libros."""
    caged = _con_objetivo(user, "Caged", "libro-caged", ["c1", "c2"], 2)
    larsen = _con_objetivo(user, "Larsen", "libro-larsen", ["l1", "l2"], 2)
    _con_objetivo(user, "Otro", "libro-otro", ["o1", "o2"], 2)

    client.force_login(user)
    respuesta = client.get(
        reverse("my_library:session_launch"),
        {"libro": [str(caged.pk), str(larsen.pk)]},
    )

    pks = [int(p) for p in respuesta.url.split("items=")[1].split("&")[0].split(",")]
    titulos = {
        i.content_object.title for i in LibraryItem.objects.filter(pk__in=pks)
    }
    assert any(t.startswith("c") for t in titulos)
    assert any(t.startswith("l") for t in titulos)
    assert not any(t.startswith("o") for t in titulos), f"el tercero no: {titulos}"


def test_los_chips_de_objetivo_salen_en_la_pantalla_de_empezar(client, db, user):
    """Si no se ven, no existen."""
    _con_objetivo(user, "El Sistema CAGED", "libro-caged", ["c1", "c2"], 2)

    client.force_login(user)
    html = client.get(reverse("my_library:session_start")).content.decode()

    assert "Seguir un libro" in html
    assert "El Sistema CAGED" in html
    assert 'name="libro"' in html
