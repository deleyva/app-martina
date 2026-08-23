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


def test_una_etiqueta_viva_en_musictag_no_se_reescribe(db, tmp_path, user):
    """La salvaguarda, con el caso real que la obligó a existir.

    Hay DOS vocabularios de etiquetas y solo uno se migró: `taggit.Tag`, que
    renombró esta migración, y `cms.MusicTag`, con su tabla aparte, intacto.
    `build_tag_map` recoge los nombres de los dos sin distinguir.

    El mazo `caged-system` del principal empareja 11 elementos por `MusicTag`,
    y `caged-system` no existe en taggit desde el 12/08. Mirar solo taggit lo
    daría por muerto y lo arrastraría a `concepto:caged`, que no tiene nada:
    de 11 a 0. Arreglando dos mazos habríamos roto el tercero.
    """
    from cms.models import MusicTag

    MusicTag.objects.create(name="caged-system")

    mazo = _mazo(user, "caged", ["caged-system"])

    _migrar(
        tmp_path, ["caged-system -> concepto:caged"], ejecutar=True, solo_mazos=True
    )

    mazo.refresh_from_db()
    assert mazo.get_tags() == ["caged-system"]  # intacto


def test_migrar_del_todo_tampoco_reescribe_lo_vivo_en_musictag(db, tmp_path, user):
    """La misma trampa en el camino normal: renombrar en taggit no borra el
    nombre en `MusicTag`, así que ese mazo tampoco se toca."""
    from cms.models import MusicTag
    from taggit.models import Tag

    MusicTag.objects.create(name="jazz")
    _item(user, "uno", tags=["jazz"])  # el 'jazz' de taggit, que sí se renombra
    mazo = _mazo(user, "jazz", ["jazz"])

    _migrar(tmp_path, ["jazz -> estilo:jazz"], ejecutar=True)

    assert Tag.objects.filter(name="estilo:jazz").exists()  # taggit sí migró
    mazo.refresh_from_db()
    assert mazo.get_tags() == ["jazz"]  # el mazo no, porque MusicTag sigue viva


def test_solo_mazos_arrastra_cuando_el_nombre_esta_muerto_en_los_dos(db, tmp_path, user):
    """El contraste: si el nombre no vive en ninguno de los dos vocabularios,
    es un puntero muerto y se arrastra. Es el caso de `instrument/guitar`."""
    item = _item(user, "uno", tags=["instrumento:guitarra"])
    mazo = _mazo(user, "guitarra", ["instrument/guitar"])

    _migrar(
        tmp_path,
        ["instrument/guitar -> instrumento:guitarra"],
        ejecutar=True,
        solo_mazos=True,
    )

    mazo.refresh_from_db()
    assert mazo.get_tags() == ["instrumento:guitarra"]
    tag_map = LibraryDeck.build_tag_map(LibraryItem.objects.filter(user=user))
    assert mazo.get_matching_item_pks(tag_map) == [item.pk]


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


# === Fase 8: mover las etiquetas de MusicTag a taggit facetado ===


def _pagina_con_musictags(titulo, slug, nombres, modelo=None, **extra):
    """Una página real bajo la raíz, con sus `MusicTag` puestas.

    Wagtail no deja crear una página suelta: necesita padre en el árbol, y por
    eso no vale con `Modelo.objects.create`. `BlogPage` además OBLIGA a
    `date` e `intro` — es el dato que sostiene el argumento 3 del debate
    ScorePage -> BlogPage, y aquí se confirma solo.
    """
    from cms.models import MusicTag, ScorePage
    from wagtail.models import Page

    modelo = modelo or ScorePage
    raiz = Page.objects.get(id=2)
    pagina = modelo(title=titulo, slug=slug, **extra)
    raiz.add_child(instance=pagina)
    for nombre in nombres:
        etiqueta, _ = MusicTag.objects.get_or_create(name=nombre)
        pagina.tags.add(etiqueta)
    pagina.save()
    return pagina


def _mapa_musictags(tmp_path, lineas):
    mapa = tmp_path / "mapa_musictags.txt"
    mapa.write_text("\n".join(lineas) + "\n")
    return mapa


def _migrar_musictags(tmp_path, lineas, ejecutar=False):
    from django.core.management import call_command

    args = ["migrar_musictags", "--mapa", str(_mapa_musictags(tmp_path, lineas))]
    if ejecutar:
        args.append("--ejecutar")
    call_command(*args)


def _plan(tmp_path, lineas):
    from my_library.management.commands.migrar_musictags import (
        leer_mapa,
        planificar_paginas,
    )

    return planificar_paginas(leer_mapa(_mapa_musictags(tmp_path, lineas)))


def test_el_plan_traduce_la_etiqueta_plana_a_su_faceta(db, tmp_path):
    _pagina_con_musictags("Blues en La", "blues-en-la", ["guitar"])

    plan = _plan(tmp_path, ["guitar -> instrumento:guitarra"])

    assert len(plan) == 1
    _pagina, viejos, nuevos, pelada = plan[0]
    assert viejos == ["guitar"]
    assert nuevos == ["instrumento:guitarra"]
    assert not pelada


def test_tres_musictags_al_mismo_destino_no_duplican(db, tmp_path):
    """`guitar`, `guitarra` y `guitar solo` van las tres a la misma faceta. Sin
    deduplicar, la escritura reventaría contra la unicidad del through model."""
    _pagina_con_musictags(
        "Metodo", "metodo", ["guitar", "guitarra", "guitar solo"]
    )

    plan = _plan(
        tmp_path,
        [
            "guitar -> instrumento:guitarra",
            "guitarra -> instrumento:guitarra",
            "guitar solo -> instrumento:guitarra",
        ],
    )

    assert plan[0][2] == ["instrumento:guitarra"]


def test_borrar_saca_la_etiqueta_del_plan(db, tmp_path):
    _pagina_con_musictags("Balada", "balada", ["guitar", "melancholic"])

    plan = _plan(
        tmp_path,
        ["guitar -> instrumento:guitarra", "melancholic -> __BORRAR__"],
    )

    assert plan[0][2] == ["instrumento:guitarra"]


def test_una_pagina_con_todo_borrado_queda_marcada(db, tmp_path):
    """No frena la migración, pero es pérdida real de información y el
    principal tiene que verla antes de aceptarla."""
    _pagina_con_musictags("Iconica", "iconica", ["iconic", "upbeat"])

    plan = _plan(tmp_path, ["iconic -> __BORRAR__", "upbeat -> __BORRAR__"])

    _pagina, viejos, nuevos, pelada = plan[0]
    assert nuevos == []
    assert pelada
    assert sorted(viejos) == ["iconic", "upbeat"]


def test_las_paginas_sin_etiquetas_no_entran_en_el_plan(db, tmp_path):
    _pagina_con_musictags("Vacia", "vacia", [])
    _pagina_con_musictags("Con etiqueta", "con-etiqueta", ["guitar"])

    plan = _plan(tmp_path, ["guitar -> instrumento:guitarra"])

    assert len(plan) == 1


def test_los_cuatro_tipos_de_pagina_entran_en_el_plan(db, tmp_path):
    from cms.models import BlogPage, DictadoPage, ScorePage, TestPage

    _pagina_con_musictags("Score", "score-g", ["guitar"], modelo=ScorePage)
    _pagina_con_musictags("Dictado", "dictado-g", ["guitar"], modelo=DictadoPage)
    _pagina_con_musictags("Test", "test-g", ["guitar"], modelo=TestPage)
    _pagina_con_musictags(
        "Blog",
        "blog-g",
        ["guitar"],
        modelo=BlogPage,
        date=timezone.now().date(),
        intro="Entrada de prueba",
    )

    plan = _plan(tmp_path, ["guitar -> instrumento:guitarra"])

    tipos = {type(p).__name__ for p, _v, _n, _s in plan}
    assert tipos == {"ScorePage", "DictadoPage", "TestPage", "BlogPage"}


def test_el_plan_es_el_mismo_se_haya_ejecutado_o_no(db, tmp_path):
    """Se aplica el MAPA, no el estado de taggit. Por eso una ejecución que se
    quedó a medias se retoma volviendo a lanzar el comando."""
    from taggit.models import Tag

    _pagina_con_musictags("Blues", "blues-idem", ["guitar"])
    antes = _plan(tmp_path, ["guitar -> instrumento:guitarra"])

    Tag.objects.create(name="instrumento:guitarra", slug="instrumento-guitarra")
    despues = _plan(tmp_path, ["guitar -> instrumento:guitarra"])

    assert [(p.pk, n) for p, _v, n, _s in antes] == [
        (p.pk, n) for p, _v, n, _s in despues
    ]


def test_una_musictag_fuera_del_mapa_aborta(db, tmp_path):
    """Si alguien etiqueta en el admin después de cerrar el mapa, esa etiqueta
    se quedaría fuera en silencio. Así es como se pierde media migración."""
    from django.core.management.base import CommandError

    _pagina_con_musictags("Nueva", "nueva", ["guitar", "bulerias"])

    with pytest.raises(CommandError, match="no están en el mapa"):
        _migrar_musictags(tmp_path, ["guitar -> instrumento:guitarra"])


def test_una_cadena_en_el_mapa_aborta(db, tmp_path):
    """`a -> b` y `b -> c` hace que ejecutar dos veces no dé lo mismo."""
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="cadenas"):
        _migrar_musictags(
            tmp_path,
            ["guitar -> guitarra", "guitarra -> instrumento:guitarra"],
        )


def test_dos_origenes_que_solo_cambian_en_mayusculas_abortan(db, tmp_path):
    """`MusicTag.name` distingue mayúsculas y el emparejamiento de mazos no.
    El resultado dependería del orden de lectura del fichero."""
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="mayúsculas"):
        _migrar_musictags(
            tmp_path,
            ["Coro -> voz:coro", "coro -> concepto:canon"],
        )


def test_una_faceta_desconocida_aborta(db, tmp_path):
    """La etiqueta nacería muerta: `facets.parse` no la reconoce, así que no
    agrupa ni filtra. Falla en silencio, que es la peor forma de fallar."""
    from django.core.management.base import CommandError

    _pagina_con_musictags("Melancolica", "melancolica", ["melancholic"])

    with pytest.raises(CommandError, match="Faceta desconocida|facetas que no existen"):
        _migrar_musictags(tmp_path, ["melancholic -> caracter:melancolico"])


def test_en_seco_no_crea_ninguna_etiqueta_en_taggit(db, tmp_path):
    from taggit.models import Tag

    _pagina_con_musictags("Blues", "blues-seco", ["guitar"])

    _migrar_musictags(tmp_path, ["guitar -> instrumento:guitarra"])

    assert not Tag.objects.filter(name="instrumento:guitarra").exists()


def test_en_seco_no_borra_ninguna_musictag(db, tmp_path):
    """Qué pasa con el modelo `MusicTag` es C37. Mezclar el movimiento con el
    borrado dejaría sin red la comprobación de paridad de C35."""
    from cms.models import MusicTag

    _pagina_con_musictags("Iconica", "iconica-seco", ["iconic"])

    _migrar_musictags(tmp_path, ["iconic -> __BORRAR__"])

    assert MusicTag.objects.filter(name="iconic").exists()


def test_el_plan_separa_lo_que_fusiona_de_lo_que_crea(db, tmp_path):
    """Con 139 etiquetas ya facetadas, un mapa sano crea muy pocas. Ver esa
    cuenta es lo que dice si el mapa fusiona con el vocabulario bueno o se
    inventa ramas nuevas."""
    from my_library.management.commands.migrar_musictags import clasificar_destinos
    from taggit.models import Tag

    Tag.objects.create(name="instrumento:guitarra", slug="instrumento-guitarra")
    _pagina_con_musictags("Dos", "dos", ["guitar", "blues"])

    plan = _plan(
        tmp_path, ["guitar -> instrumento:guitarra", "blues -> estilo:blues"]
    )
    conteo, por_crear = clasificar_destinos(plan)

    assert conteo == {"instrumento:guitarra": 1, "estilo:blues": 1}
    assert por_crear == ["estilo:blues"]


def test_las_cuatro_paginas_tienen_manager_de_taggit(db):
    """C33. El campo nace VACÍO y al lado de `tags`, no en su lugar: renombrar de
    golpe abriría una ventana con `build_tag_map` leyendo un campo vacío."""
    from cms.models import BlogPage, DictadoPage, ScorePage, TestPage
    from my_library.management.commands.migrar_musictags import (
        CAMPO_DESTINO,
        campo_destino_existe,
    )

    assert campo_destino_existe()
    for modelo in (BlogPage, ScorePage, DictadoPage, TestPage):
        campos = {f.name for f in modelo._meta.get_fields()}
        assert CAMPO_DESTINO in campos, modelo.__name__
        assert "tags" in campos, f"{modelo.__name__} perdió el vocabulario viejo"


def test_el_campo_nuevo_nace_vacio(db):
    """Si naciera con algo dentro, este despliegue cambiaría lo que ve alguien."""
    from cms.models import ScorePage

    pagina = _pagina_con_musictags("Recien creada", "recien", ["guitar"])
    assert pagina.faceted_tags.count() == 0
    assert ScorePage.objects.get(pk=pagina.pk).faceted_tags.count() == 0


def test_en_seco_no_escribe_aunque_el_campo_ya_exista(db, tmp_path):
    """Con C33 puesta ya no hay guardia que pare `--ejecutar`, así que lo único
    que separa un ensayo de una migración es la ausencia de la bandera."""
    from taggit.models import Tag

    pagina = _pagina_con_musictags("Blues", "blues-seco-c33", ["guitar"])

    _migrar_musictags(tmp_path, ["guitar -> instrumento:guitarra"])

    assert pagina.faceted_tags.count() == 0
    assert not Tag.objects.filter(name="instrumento:guitarra").exists()


def test_el_informe_cuenta_lo_que_se_pierde(db, tmp_path):
    """Un resumen que solo cuenta lo que se gana invita a aprobar una migración
    sin mirar lo que borra."""
    from my_library.management.commands.migrar_musictags import (
        etiquetados_que_se_pierden,
        leer_mapa,
    )

    _pagina_con_musictags("Una", "perd-1", ["guitar", "iconic"])
    _pagina_con_musictags("Otra", "perd-2", ["iconic", "upbeat"])

    mapa = leer_mapa(
        _mapa_musictags(
            tmp_path,
            [
                "guitar -> instrumento:guitarra",
                "iconic -> __BORRAR__",
                "upbeat -> __BORRAR__",
            ],
        )
    )
    perdidos, paginas = etiquetados_que_se_pierden(mapa)

    assert perdidos == {"iconic": 2, "upbeat": 1}
    assert paginas == 2


# === C34b: escribir las etiquetas en las páginas ===


def test_aplicar_escribe_las_etiquetas_facetadas(db, tmp_path):
    from cms.models import ScorePage

    pagina = _pagina_con_musictags("Blues", "aplicar-1", ["guitar", "blues"])

    _migrar_musictags(
        tmp_path,
        ["guitar -> instrumento:guitarra", "blues -> estilo:blues"],
        ejecutar=True,
    )

    releida = ScorePage.objects.get(pk=pagina.pk)
    assert {t.name for t in releida.faceted_tags.all()} == {
        "instrumento:guitarra",
        "estilo:blues",
    }


def test_aplicar_no_toca_el_vocabulario_viejo(db, tmp_path):
    """`MusicTag` se decide en C37. Mezclar el movimiento con el borrado deja
    sin red la comprobación de paridad de C35."""
    from cms.models import MusicTag, ScorePage

    pagina = _pagina_con_musictags("Blues", "aplicar-2", ["guitar"])

    _migrar_musictags(tmp_path, ["guitar -> instrumento:guitarra"], ejecutar=True)

    releida = ScorePage.objects.get(pk=pagina.pk)
    assert {t.name for t in releida.tags.all()} == {"guitar"}
    assert MusicTag.objects.filter(name="guitar").exists()


def test_aplicar_es_idempotente(db, tmp_path):
    from cms.models import ScorePage

    pagina = _pagina_con_musictags("Blues", "aplicar-3", ["guitar", "guitarra"])
    lineas = [
        "guitar -> instrumento:guitarra",
        "guitarra -> instrumento:guitarra",
    ]

    _migrar_musictags(tmp_path, lineas, ejecutar=True)
    _migrar_musictags(tmp_path, lineas, ejecutar=True)

    releida = ScorePage.objects.get(pk=pagina.pk)
    assert [t.name for t in releida.faceted_tags.all()] == ["instrumento:guitarra"]


def test_publicar_un_borrador_viejo_no_se_lleva_las_etiquetas(db, tmp_path):
    """LA PREGUNTA QUE DECIDE C34b.

    37 de las 300 páginas de producción tienen un borrador sin publicar, creado
    ANTES de que existiera `faceted_tags`. Si escribir solo en la fila viva basta,
    publicar ese borrador después borraría las etiquetas nuevas — una migración
    que se deshace sola semanas más tarde y sin que nadie la toque.
    """
    from cms.models import ScorePage

    pagina = _pagina_con_musictags("Blues", "aplicar-4", ["guitar"])
    revision_vieja = pagina.save_revision()  # borrador de antes de etiquetar

    _migrar_musictags(tmp_path, ["guitar -> instrumento:guitarra"], ejecutar=True)
    assert {t.name for t in ScorePage.objects.get(pk=pagina.pk).faceted_tags.all()} == {
        "instrumento:guitarra"
    }

    # Releída de la BD, que es lo que hace el admin al publicar. El objeto que
    # quedó en memoria lleva el `content` de antes de migrar y publicarlo
    # probaría algo que no pasa nunca por la interfaz.
    from wagtail.models import Revision

    Revision.objects.get(pk=revision_vieja.pk).publish()

    releida = ScorePage.objects.get(pk=pagina.pk)
    assert {t.name for t in releida.faceted_tags.all()} == {"instrumento:guitarra"}, (
        "publicar un borrador anterior a la migración se ha llevado las etiquetas"
    )
