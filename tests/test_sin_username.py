"""En este proyecto `User.username` no existe (USERNAME_FIELD = "email").

Toda búsqueda del admin que recorra `__username` revienta con FieldError, y
todo `user.username` pinta "None". Fase 88: estas pruebas fijan los sitios que
se arreglaron para que no vuelvan.
"""

from http import HTTPStatus

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "changelist",
    [
        "admin:evaluations_submissionvideo_changelist",
        "admin:songs_ranking_songproposal_changelist",
        "admin:songs_ranking_vote_changelist",
    ],
)
def test_buscar_en_el_admin_no_revienta(admin_client, changelist):
    response = admin_client.get(reverse(changelist), data={"q": "ana"})
    assert response.status_code == HTTPStatus.OK


def _admins_con_busqueda():
    from django.contrib import admin

    return sorted(
        f"admin:{m._meta.app_label}_{m._meta.model_name}_changelist"
        for m, ma in admin.site._registry.items()
        if ma.search_fields
    )


def test_buscar_en_cualquier_admin_no_revienta(admin_client):
    """La versión universal: un `search_fields` con un campo que no existe
    (`__username`, `video_file`…) solo revienta al buscar, y `manage.py check`
    no lo ve. Se recorre cada admin registrado con buscador."""
    rotos = []
    for changelist in _admins_con_busqueda():
        try:
            status = admin_client.get(reverse(changelist), data={"q": "ana"}).status_code
        except Exception as exc:  # noqa: BLE001 — se quiere la lista entera, no el primero
            status = type(exc).__name__
        if status != HTTPStatus.OK:
            rotos.append((changelist, status))
    assert rotos == []


def test_el_filtro_guardado_se_nombra_por_correo(django_user_model):
    from cms.models import SavedResourceFilter

    user = django_user_model.objects.create_user(email="ana@example.com", password="x")
    filtro = SavedResourceFilter(user=user, name="Lecturas")
    assert str(filtro) == "ana@example.com - Lecturas"
