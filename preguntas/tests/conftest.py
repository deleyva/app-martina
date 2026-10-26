import datetime as dt

import pytest

from clases.models import ClassSession, Group, Subject
from martina_bescos_app.users.tests.factories import UserFactory


@pytest.fixture
def profesor(db):
    return UserFactory(name="Profe Preguntas", is_staff=True)


@pytest.fixture
def alumno(db):
    return UserFactory(name="Alumno Preguntas")


@pytest.fixture
def grupo(db, profesor):
    asignatura = Subject.objects.create(name="Música")
    grupo = Group.objects.create(name="3º ESO Z", subject=asignatura, academic_year="2026-2027")
    grupo.teachers.add(profesor)
    return grupo


@pytest.fixture
def hoy():
    return dt.date(2026, 10, 26)


def sesion(grupo, fecha, titulo="Clase"):
    return ClassSession.objects.create(
        teacher=grupo.teachers.first(), group=grupo, date=fecha, title=titulo
    )


def pregunta(enunciado="¿Cuántas corcheas caben en una negra?", correcta=1, etiquetas=("concepto:figuras",), estado="activa", **extra):
    from preguntas.models import Pregunta

    p = Pregunta.objects.create(
        enunciado=enunciado,
        opciones=["Una", "Dos", "Tres", "Cuatro"],
        correcta=correcta,
        estado=estado,
        **extra,
    )
    p.etiquetas.set(list(etiquetas))
    return p
