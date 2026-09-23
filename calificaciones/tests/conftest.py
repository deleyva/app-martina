"""Fixtures propias: el `conftest` de `martina_bescos_app` no alcanza a esta app."""

from decimal import Decimal

import pytest

from calificaciones.models import Criterio, Instrumento, MarcoEvaluacion, Plan, Reparto
from clases.models import Enrollment, Group, Subject
from martina_bescos_app.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def profesor(db):
    return UserFactory(name="Profe A")


@pytest.fixture
def otro_profesor(db):
    return UserFactory(name="Profe B")


@pytest.fixture
def subject(db):
    subject, _ = Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})
    return subject


@pytest.fixture
def group(db, subject, profesor):
    group = Group.objects.create(name="3º ESO T", subject=subject, academic_year="2026-2027")
    group.teachers.add(profesor)
    return group


@pytest.fixture
def otro_group(db, subject, otro_profesor):
    group = Group.objects.create(name="3º ESO Z", subject=subject, academic_year="2026-2027")
    group.teachers.add(otro_profesor)
    return group


@pytest.fixture
def alumnos(db, group):
    alumnos = [UserFactory(name=f"Alumno {n}") for n in range(3)]
    for a in alumnos:
        Enrollment.objects.create(user=a, group=group)
    return alumnos


@pytest.fixture
def marco(db, subject):
    marco = MarcoEvaluacion.objects.create(
        subject=subject, nivel="3º ESO", academic_year="2026-2027", peso_trimestres={"1": 20, "2": 30, "3": 50}
    )
    for orden, codigo in enumerate(["1.1", "1.2", "2.1", "3.1"]):
        Criterio.objects.create(
            marco=marco, codigo=codigo, competencia="CE", descripcion=f"Criterio {codigo}", peso=Decimal(25), orden=orden
        )
    return marco


@pytest.fixture
def plan(db, marco, group):
    """Cuatro instrumentos repartidos entre dos criterios cada uno; cuadra: 25 por fila, 100 en total.

    Columnas: Teoría 30, Lectura rítmica 20, Dictado 25, Cuaderno 25.
    """
    plan = Plan.objects.create(marco=marco, trimestre=1, nombre="Plan test")
    plan.groups.add(group)
    criterios = {c.codigo: c for c in marco.criterios.all()}
    reparto = {
        "Teoría": ("Teo", {"1.1": 15, "1.2": 15}),
        "Lectura rítmica": ("L.rít", {"2.1": 10, "3.1": 10}),
        "Dictado": ("Dict", {"1.1": 10, "3.1": 15}),
        "Cuaderno": ("Cuad", {"1.2": 10, "2.1": 15}),
    }
    for orden, (nombre, (abrev, celdas)) in enumerate(reparto.items()):
        instrumento = Instrumento.objects.create(plan=plan, nombre=nombre, abreviatura=abrev, orden=orden)
        for codigo, pct in celdas.items():
            Reparto.objects.create(instrumento=instrumento, criterio=criterios[codigo], porcentaje=Decimal(pct))
    return plan
