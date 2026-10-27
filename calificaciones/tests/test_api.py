"""Fase 81 — API de lectura de calificaciones. Los falsadores de C512 a C517."""

from datetime import date
from decimal import Decimal

import pytest

from api_keys.models import APIKey
from calificaciones.models import CambioNota
from calificaciones.models import Evidencia
from calificaciones.models import Nota
from calificaciones.models import Prueba
from calificaciones.models import RevisionCuaderno
from clases.models import ClassSession
from clases.models import Enrollment
from martina_bescos_app.users.tests.factories import UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("_hosts")]

BASE = "/api/calificaciones"


@pytest.fixture
def _hosts(settings):
    settings.ALLOWED_HOSTS = ["*"]
    settings.APPS_CANDADO = False


@pytest.fixture
def clave(profesor):
    return str(APIKey.objects.create(user=profesor, name="illa").key)


@pytest.fixture
def clave_ajena(otro_profesor):
    return str(APIKey.objects.create(user=otro_profesor, name="otra").key)


@pytest.fixture
def api(client, clave):
    def llamar(ruta, clave_=clave, **params):
        return client.get(BASE + ruta, params, HTTP_X_API_KEY=clave_)

    return llamar


@pytest.fixture
def alumnos_ajenos(otro_group):
    lista = [UserFactory(name="Zoe Ajena")]
    for a in lista:
        Enrollment.objects.create(user=a, group=otro_group)
    return lista


@pytest.fixture
def prueba(plan):
    """La prueba que cada instrumento trae de serie; si no la hubiera, una."""
    teoria = plan.instrumentos.get(nombre="Teoría")
    return teoria.pruebas.first() or Prueba.objects.create(
        instrumento=teoria,
        nombre="Teoría",
        fecha=date(2026, 10, 6),
    )


@pytest.fixture
def nota(prueba, alumnos, profesor):
    nota = Nota.objects.create(
        prueba=prueba,
        alumno=alumnos[0],
        valor=Decimal("8"),
        updated_by=profesor,
    )
    CambioNota.objects.create(nota=nota, antes="", despues="8", user=profesor)
    return nota


# ----- C512: la clave manda, y solo ve lo suyo ---------------------------------------


def test_sin_clave_es_401(client, group):
    assert client.get(f"{BASE}/grupos").status_code == 401
    assert client.get(f"{BASE}/grupos/{group.pk}").status_code == 401


def test_grupos_son_solo_los_mios(api, group, otro_group, plan):
    r = api("/grupos")
    assert r.status_code == 200
    nombres = [g["nombre"] for g in r.json()]
    assert nombres == [group.name]
    ficha = r.json()[0]
    assert ficha["planes"]["1"]["id"] == plan.pk
    assert ficha["planes"]["2"] is None
    assert ficha["materia"] == "Música"


def test_el_grupo_de_otro_profesor_es_404(api, otro_group, group, plan, clave_ajena):
    assert api(f"/grupos/{otro_group.pk}").status_code == 404
    assert api(f"/grupos/{otro_group.pk}/historial").status_code == 404
    assert api(f"/grupos/{otro_group.pk}/cuaderno").status_code == 404
    # Y al revés: la clave del otro no ve el mío.
    assert api(f"/grupos/{group.pk}", clave_=clave_ajena).status_code == 404


# ----- C513: el estado del grupo es el de la pantalla -------------------------------


def test_el_estado_del_grupo_trae_las_celdas_y_las_cifras(
    api,
    group,
    alumnos,
    plan,
    prueba,
    nota,
):
    r = api(f"/grupos/{group.pk}")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["grupo"]["id"] == group.pk
    columnas = cuerpo["trimestres"]["1"]["columnas"]
    assert (
        len(columnas) == 4
    )  # una por instrumento: Teoría, Lectura rítmica, Dictado, Cuaderno
    assert prueba.pk in [c["prueba"] for c in columnas]
    por_id = {a["id"]: a for a in cuerpo["alumnos"]}
    assert len(por_id) == 3
    celda = por_id[alumnos[0].pk]["trimestres"]["1"]["notas"][str(prueba.pk)]
    assert celda["valor"] == "8"
    assert (
        por_id[alumnos[1].pk]["trimestres"]["1"]["notas"][str(prueba.pk)]["valor"] == ""
    )
    assert por_id[alumnos[0].pk]["trimestres"]["1"]["con_datos"] is True
    assert por_id[alumnos[0].pk]["curso"]["nota"] != ""


# ----- C514: historial y cuaderno ---------------------------------------------------


def test_el_historial_dice_quien_puso_que(api, group, alumnos, nota, profesor):
    r = api(f"/grupos/{group.pk}/historial")
    assert r.status_code == 200
    cambios = r.json()["cambios"]
    assert len(cambios) == 1
    assert cambios[0]["alumno_id"] == alumnos[0].pk
    assert cambios[0]["columna"] == "Teoría"
    assert cambios[0]["antes"] == ""
    assert cambios[0]["despues"] == "8"
    assert cambios[0]["quien"] == profesor.name
    assert api(f"/grupos/{group.pk}/historial", limite=0).status_code == 422


def test_el_cuaderno_trae_las_revisiones_con_letra(api, group, alumnos, plan, profesor):
    cuaderno = plan.instrumentos.get(nombre="Cuaderno")
    sesion = ClassSession.objects.create(
        teacher=profesor,
        group=group,
        date=date(2026, 10, 7),
        title="Ritmo",
    )
    RevisionCuaderno.objects.create(
        session=sesion,
        alumno=alumnos[0],
        instrumento=cuaderno,
        letra="NT",
        valor=Decimal("8"),
        autor=profesor,
    )
    RevisionCuaderno.objects.create(
        session=sesion,
        alumno=alumnos[1],
        instrumento=cuaderno,
        letra="",
    )
    r = api(f"/grupos/{group.pk}/cuaderno")
    assert r.status_code == 200
    revisiones = r.json()["revisiones"]
    assert [(x["alumno"], x["letra"], x["valor"], x["fecha"]) for x in revisiones] == [
        (alumnos[0].pk, "NT", "8", "2026-10-07"),
    ]


# ----- C515–C516: ¿es alumno mío? y su ficha ----------------------------------------


def test_buscar_alumnos_solo_entre_los_mios(api, group, alumnos, alumnos_ajenos):
    r = api("/alumnos", q="alumno")
    assert r.status_code == 200
    assert sorted(a["nombre"] for a in r.json()) == ["Alumno 0", "Alumno 1", "Alumno 2"]
    assert r.json()[0]["grupos"] == [{"id": group.pk, "nombre": group.name}]
    assert api("/alumnos", q="Ajena").json() == []
    assert api("/alumnos", q="Zoe").json() == []
    assert api("/alumnos", q="a").status_code == 422


def test_buscar_por_correo_y_sin_repetir_al_que_esta_en_dos_grupos(
    api,
    group,
    alumnos,
    subject,
    profesor,
):
    from clases.models import Group

    segundo = Group.objects.create(
        name="3º ESO U",
        subject=subject,
        academic_year="2026-2027",
    )
    segundo.teachers.add(profesor)
    Enrollment.objects.create(user=alumnos[0], group=segundo)
    r = api("/alumnos", q=alumnos[0].email[:8])
    encontrados = [a for a in r.json() if a["id"] == alumnos[0].pk]
    assert len(encontrados) == 1
    assert sorted(g["nombre"] for g in encontrados[0]["grupos"]) == sorted(
        [group.name, segundo.name],
    )


def test_la_ficha_del_alumno_reune_notas_evidencias_cuaderno_y_cambios(
    api,
    group,
    alumnos,
    plan,
    prueba,
    nota,
    profesor,
):
    Evidencia.objects.create(
        prueba=prueba,
        alumno=alumnos[0],
        tipo=Evidencia.TEXTO,
        texto="Bien",
        created_by=profesor,
    )
    r = api(f"/alumnos/{alumnos[0].pk}")
    assert r.status_code == 200
    ficha = r.json()
    assert ficha["nombre"] == "Alumno 0"
    assert ficha["grupos"] == [{"id": group.pk, "nombre": group.name}]
    (por_grupo,) = ficha["fichas"]
    assert por_grupo["grupo"]["id"] == group.pk
    assert (
        por_grupo["calificaciones"]["trimestres"]["1"]["notas"][str(prueba.pk)]["valor"]
        == "8"
    )
    assert [e["texto"] for e in por_grupo["evidencias"]] == ["Bien"]
    assert por_grupo["cuaderno"] == []
    assert [(c["columna"], c["despues"]) for c in por_grupo["cambios"]] == [
        ("Teoría", "8"),
    ]


def test_el_alumno_de_otro_profesor_o_dado_de_baja_es_404(
    api,
    group,
    alumnos,
    alumnos_ajenos,
):
    assert api(f"/alumnos/{alumnos_ajenos[0].pk}").status_code == 404
    Enrollment.objects.filter(user=alumnos[1], group=group).update(is_active=False)
    assert api(f"/alumnos/{alumnos[1].pk}").status_code == 404
    assert api("/alumnos", q="Alumno 1").json() == []
