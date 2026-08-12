import json
import uuid
from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from cms.models import ExternalResource
from martina_bescos_app.users.tests.factories import UserFactory
from my_library.models import LibraryDeck, LibraryItem, ReviewLog


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
