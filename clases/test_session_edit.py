# ruff: noqa: S101
"""La edición de sesión sin biblioteca de grupo (fase 89).

Este fichero probaba el buscador y el «Mostrar más» del panel de biblioteca de
la edición de sesión. El panel salió de la pantalla el 2026-09-08 (fase 28) y el
modelo, en la fase 89. Queda lo que sigue importando: que la página abre.
"""
import pytest
from django.urls import reverse

from clases.models import ClassSession
from clases.models import Group
from clases.models import Subject
from martina_bescos_app.users.tests.factories import UserFactory


@pytest.fixture
def staff_user(db):
    return UserFactory(is_staff=True)


@pytest.fixture
def session(db, staff_user):
    subject, _ = Subject.objects.get_or_create(
        code="MUS", defaults={"name": "Música"}
    )
    grupo = Group.objects.create(name="4AG", subject=subject)
    grupo.teachers.add(staff_user)
    return ClassSession.objects.create(
        teacher=staff_user, group=grupo, date="2026-02-12", title="Test Session"
    )


@pytest.mark.django_db
def test_la_edicion_abre_sin_biblioteca_de_grupo(client, staff_user, session):
    client.force_login(staff_user)

    response = client.get(reverse("clases:class_session_edit", args=[session.pk]))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Contenido de la Sesión" in html
    # Ni el panel ni los contadores que vivían en sus filas.
    assert "Biblioteca del Grupo" not in html
    assert "storeCounterData" not in html
    assert "scorepage-total-count" not in html
