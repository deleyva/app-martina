import pytest

from martina_bescos_app.users.tests.factories import UserFactory


@pytest.fixture
def profesor(db):
    return UserFactory(name="Profe Preguntas", is_staff=True)


@pytest.fixture
def alumno(db):
    return UserFactory(name="Alumno Preguntas")
