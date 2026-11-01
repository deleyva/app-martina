"""Fase 92 — La banda del grupo: la rejilla del curso y la banda de hoy. Los falsadores de C615 a C623."""

import json
import random
from datetime import date
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from clases import banda as bandas
from clases.models import Asistencia
from clases.models import BandaDeGrupo
from clases.models import BandaVersion
from clases.models import CambioDeHoy
from clases.models import ClassSession
from clases.models import Enrollment
from clases.models import Group
from clases.models import PaseDeLista
from clases.models import Subject
from martina_bescos_app.users.tests.factories import UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("_hosts")]

INICIO = date(2026, 9, 14)


@pytest.fixture
def _hosts(settings):
    settings.ALLOWED_HOSTS = ["*"]
    settings.APPS_CANDADO = False


def _grupo(nombre, profesor=None):
    asignatura, _ = Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})
    grupo = Group.objects.create(name=nombre, subject=asignatura, academic_year="2026-2027")
    if profesor:
        grupo.teachers.add(profesor)
    return grupo


def _matricular(grupo, n, prefijo="ALUMNO"):
    lista = [UserFactory(name=f"{prefijo} {i:02d} APELLIDO") for i in range(n)]
    for a in lista:
        Enrollment.objects.create(user=a, group=grupo)
    return lista


@pytest.fixture
def profesor():
    return UserFactory(name="Profe")


@pytest.fixture
def grupo(profesor):
    return _grupo("1-G-BIL", profesor)


@pytest.fixture
def treinta(grupo):
    return _matricular(grupo, 30)


@pytest.fixture
def banda(grupo, treinta, profesor):
    return bandas.crear(grupo, autor=profesor, hoy=INICIO)


@pytest.fixture
def grupo4(profesor):
    return _grupo("4AG", profesor)


@pytest.fixture
def siete(grupo4):
    return _matricular(grupo4, 7, prefijo="CUARTO")


@pytest.fixture
def banda4(grupo4, siete, profesor):
    return bandas.crear(grupo4, autor=profesor, hoy=INICIO)


def _sesion(grupo, profesor, dia, aula="musica", cerrada=True):
    s = ClassSession.objects.create(teacher=profesor, group=grupo, date=INICIO + timedelta(days=dia), title=f"Día {dia}")
    PaseDeLista.objects.create(session=s, aula=aula)
    if cerrada:
        s.closed_at = timezone.now()
        s.save(update_fields=["closed_at"])
    return s


def _clave(turno, alumno):
    for c, a in zip(turno["plazas"], turno["alumnos"]):
        if a == alumno:
            return c
    return None


# === C615 — puestos y valores por defecto ===


@pytest.mark.parametrize("nombre", ["1-G-BIL", "3-EG", "3 ESO T"])
def test_1_y_3_nacen_en_rotacion_con_seis_puestos(profesor, nombre):
    g = _grupo(nombre, profesor)
    b = bandas.crear(g, hoy=INICIO)
    assert b.modo == BandaDeGrupo.ROTACION
    assert b.puestos == ["bateria", "ukebajo", "teclado", "electrica", "guitalele", "espanola"]
    assert b.turnos == 16 and b.sesiones_por_turno == 2
    assert len(b.plan["turnos"]) == 16
    assert all(t["alumnos"] == [None] * 6 for t in b.plan["turnos"])


def test_4_nace_en_intercambio_con_siete_plazas(banda4):
    assert banda4.modo == BandaDeGrupo.INTERCAMBIO
    assert banda4.puestos == ["bateria", "bajo", "teclado", "teclado", "electrica", "espanola", "voz"]
    assert banda4.turnos == 15
    assert bandas.etiquetas_de_plazas(banda4.puestos)[2:4] == ["Teclado 1", "Teclado 2"]


def test_cada_puesto_dice_sus_filas_y_si_es_portatil():
    assert bandas.PUESTOS["bateria"].filas == ("SH", "CA", "BO")
    assert bandas.PUESTOS["ukebajo"].filas == ("BA",) and bandas.PUESTOS["ukebajo"].portatil
    assert not bandas.PUESTOS["teclado"].portatil
    assert {"ukebajo", "guitalele", "espanola", "cajon"} == {c for c, p in bandas.PUESTOS.items() if p.portatil}


# === C616 — la rotación es justa, de forma universal ===


def _comprobar_rotacion(plan, ids):
    turnos = plan["turnos"]
    total = dict.fromkeys(ids, 0)
    primeros = {a: [] for a in ids}
    for n, t in enumerate(turnos, start=1):
        dentro = [a for a in t["alumnos"] if a is not None]
        assert len(dentro) == len(t["plazas"]), f"turno {n} con huecos"
        assert len(set(dentro)) == len(dentro), f"turno {n}: alguien con dos plazas"
        fuera = [a for a in ids if a not in dentro]
        # Nadie repite banda hasta que todos han pasado: el más rodado de los
        # que entran no lleva más turnos que el menos rodado de los que no.
        assert max(total[a] for a in dentro) <= min(total[a] for a in fuera), f"turno {n}"
        if n > 1:
            for a in dentro:
                assert _clave(t, a) is None or _clave(t, a) != _clave(turnos[n - 2], a), f"turno {n}: repite seguido"
        for a in dentro:
            total[a] += 1
            primeros[a].append(_clave(t, a))
    assert max(total.values()) - min(total.values()) <= 1
    return primeros


def test_400_generaciones_de_rotacion_son_justas(banda, treinta):
    ids = [a.pk for a in treinta]
    distintos_en_los_tres_primeros = 0
    for semilla in range(400):
        plan = bandas.planificar(banda, 1, azar=random.Random(semilla))
        primeros = _comprobar_rotacion(plan, ids)
        distintos_en_los_tres_primeros += sum(1 for v in primeros.values() if len(set(v[:3])) == 3)
    # Cada alumno pasa tres veces como mínimo, y cada vez con un instrumento nuevo.
    assert distintos_en_los_tres_primeros == 400 * 30


def test_la_rotacion_con_semilla_es_reproducible(banda):
    a = bandas.planificar(banda, 1, azar=random.Random(7))
    b = bandas.planificar(banda, 1, azar=random.Random(7))
    assert a == b


def test_un_bloqueo_se_respeta(banda, treinta):
    banda.bloqueos = {str(treinta[0].pk): ["bateria"]}
    banda.save()
    for semilla in range(50):
        plan = bandas.planificar(banda, 1, azar=random.Random(semilla))
        assert all(_clave(t, treinta[0].pk) != "bateria" for t in plan["turnos"])


# === C617 — generar respeta lo fijado y lo jugado ===


def test_lo_fijado_no_se_mueve(banda, treinta, profesor):
    bandas.poner(banda, 1, 0, treinta[5].pk, autor=profesor)
    bandas.poner(banda, 5, 2, treinta[9].pk, autor=profesor)
    for semilla in range(20):
        bandas.generar(banda, autor=profesor, azar=random.Random(semilla))
        banda.refresh_from_db()
        t1, t5 = banda.plan["turnos"][0], banda.plan["turnos"][4]
        assert t1["alumnos"][0] == treinta[5].pk and 0 in t1["fijadas"]
        assert t5["alumnos"][2] == treinta[9].pk and 2 in t5["fijadas"]


def test_lo_jugado_no_cambia_al_regenerar(banda, grupo, profesor):
    bandas.generar(banda, autor=profesor, azar=random.Random(1))
    for dia in range(3):  # turno 1 entero y la primera sesión del 2
        _sesion(grupo, profesor, dia)
    banda.refresh_from_db()
    assert bandas.posicion(banda).turno == 2 and bandas.primer_turno_libre(banda) == 3
    antes = [dict(t) for t in banda.plan["turnos"][:2]]
    resto = [dict(t) for t in banda.plan["turnos"][2:]]
    bandas.generar(banda, autor=profesor, azar=random.Random(99))
    banda.refresh_from_db()
    assert banda.plan["turnos"][:2] == antes
    assert banda.plan["turnos"][2:] != resto  # y lo de después sí se ha rehecho


def test_generar_rellena_los_huecos_del_turno_en_curso_sin_mover_a_nadie(banda, grupo, profesor):
    bandas.generar(banda, autor=profesor, azar=random.Random(1))
    _sesion(grupo, profesor, 0)  # el turno 1 ha empezado
    banda.refresh_from_db()
    bandas.poner(banda, 1, 3, None, autor=profesor)
    banda.refresh_from_db()
    antes = list(banda.plan["turnos"][0]["alumnos"])
    bandas.generar(banda, autor=profesor, azar=random.Random(2))
    banda.refresh_from_db()
    despues = banda.plan["turnos"][0]["alumnos"]
    assert despues[3] is not None
    assert [a for i, a in enumerate(despues) if i != 3] == [a for i, a in enumerate(antes) if i != 3]


def test_una_baja_sale_de_los_turnos_futuros_y_no_de_los_jugados(banda, grupo, profesor):
    bandas.generar(banda, autor=profesor, azar=random.Random(3))
    for dia in range(2):
        _sesion(grupo, profesor, dia)
    banda.refresh_from_db()
    t1 = banda.plan["turnos"][0]["alumnos"]
    baja = t1[0]
    Enrollment.objects.filter(user_id=baja, group=grupo).update(is_active=False)
    bandas.generar(banda, autor=profesor, azar=random.Random(4))
    banda.refresh_from_db()
    assert banda.plan["turnos"][0]["alumnos"][0] == baja
    assert all(baja not in t["alumnos"] for t in banda.plan["turnos"][1:])


def test_generar_deja_version_y_se_deshace(banda, profesor):
    bandas.generar(banda, autor=profesor, azar=random.Random(5))
    banda.refresh_from_db()
    assert banda.versiones.first().origen == BandaVersion.GENERAR
    vacia = banda.versiones.get(origen=BandaVersion.CONFIGURAR)
    bandas.restaurar(vacia, autor=profesor)
    banda.refresh_from_db()
    assert all(a is None for t in banda.plan["turnos"] for a in t["alumnos"])


# === C618 — la regla de intercambio (4º) ===


def test_200_cursos_de_intercambio_cambian_dos_y_el_mejor_cambio(banda4, siete):
    ids = {a.pk for a in siete}
    for semilla in range(200):
        plan = bandas.planificar(banda4, 1, azar=random.Random(semilla))
        turnos = plan["turnos"]
        for n, t in enumerate(turnos, start=1):
            assert set(t["alumnos"]) == ids, f"turno {n}: alguien sin plaza"
            if n == 1:
                continue
            previo = turnos[n - 2]
            distintas = [i for i in range(7) if t["alumnos"][i] != previo["alumnos"][i]]
            assert len(distintas) == 2, f"semilla {semilla}, turno {n}: {distintas}"
            i, j = distintas
            assert t["plazas"][i] != t["plazas"][j]
            # El cambio elegido es el de más ganancia de todos los posibles.
            historial = bandas.Historial.hasta(plan, n)
            elegido = bandas.mejor_intercambio(previo["plazas"], previo["alumnos"], historial, azar=random.Random(0))

            def ganancia(a, b):
                h = historial.veces
                x, y = previo["alumnos"][a], previo["alumnos"][b]
                return int(previo["plazas"][b] not in h.get(x, {})) + int(previo["plazas"][a] not in h.get(y, {}))

            assert ganancia(i, j) == elegido[2]
            assert elegido[2] == max(
                ganancia(a, b) for a in range(7) for b in range(a + 1, 7) if previo["plazas"][a] != previo["plazas"][b]
            )


# === C619 — el turno vigente sale de las sesiones ===


def test_el_turno_avanza_cada_dos_sesiones_en_musica(banda, grupo, profesor):
    assert bandas.posicion(banda) == bandas.Posicion(1, 1, 2)
    _sesion(grupo, profesor, 0)
    assert bandas.posicion(banda) == bandas.Posicion(1, 2, 2)
    _sesion(grupo, profesor, 1, aula="referencia")  # no cuenta
    _sesion(grupo, profesor, 2, cerrada=False)  # abierta: aún no cuenta
    assert bandas.posicion(banda).turno == 1
    _sesion(grupo, profesor, 3)
    assert bandas.posicion(banda) == bandas.Posicion(2, 1, 2)


def test_contando_todas_cuenta_tambien_el_aula_de_referencia(banda, grupo, profesor):
    banda.cuenta = BandaDeGrupo.CUENTA_TODAS
    banda.save()
    _sesion(grupo, profesor, 0, aula="referencia")
    _sesion(grupo, profesor, 1)
    assert bandas.posicion(banda).turno == 2


def test_lo_anterior_al_inicio_no_cuenta(banda, grupo, profesor):
    _sesion(grupo, profesor, -3)
    assert bandas.posicion(banda) == bandas.Posicion(1, 1, 2)


def test_ajustar_adelanta_y_atrasa_un_turno_entero(banda, grupo, profesor):
    _sesion(grupo, profesor, 0)
    bandas.ajustar(banda, +1)
    banda.refresh_from_db()
    assert bandas.posicion(banda) == bandas.Posicion(2, 1, 2)
    bandas.ajustar(banda, -1)
    banda.refresh_from_db()
    assert bandas.posicion(banda) == bandas.Posicion(1, 1, 2)
    bandas.ajustar(banda, -1)  # no baja del turno 1
    banda.refresh_from_db()
    assert bandas.posicion(banda) == bandas.Posicion(1, 1, 2)


def test_cambiar_las_sesiones_por_turno_no_mueve_el_turno_vigente(banda, grupo, profesor):
    for dia in range(3):
        _sesion(grupo, profesor, dia)
    assert bandas.posicion(banda) == bandas.Posicion(2, 2, 2)
    bandas.configurar(
        banda, modo=banda.modo, puestos=banda.puestos, sesiones_por_turno=1, turnos=banda.turnos,
        empieza=banda.empieza, cuenta=banda.cuenta,
    )
    banda.refresh_from_db()
    assert bandas.posicion(banda).turno == 2
    _sesion(grupo, profesor, 5)
    assert bandas.posicion(banda).turno == 3


def test_una_sesion_cerrada_se_ve_en_su_turno(banda, grupo, profesor):
    s1 = _sesion(grupo, profesor, 0)
    _sesion(grupo, profesor, 1)
    _sesion(grupo, profesor, 2)
    assert bandas.posicion(banda, s1) == bandas.Posicion(1, 1, 2)
    assert bandas.posicion(banda).turno == 2


# === C620 — la rejilla del curso ===


def test_la_rejilla_sin_banda_ofrece_crearla(client, profesor, grupo, treinta):
    client.force_login(profesor)
    r = client.get(reverse("clases:banda_rejilla", args=[grupo.pk]))
    assert r.status_code == 200
    assert b'id="crear-banda"' in r.content
    assert b"{#" not in r.content
    r = client.post(reverse("clases:banda_crear", args=[grupo.pk]))
    assert r.status_code == 302
    assert BandaDeGrupo.objects.filter(group=grupo).exists()


def test_la_rejilla_pinta_los_turnos_y_marca_el_vigente(client, profesor, grupo, banda):
    bandas.generar(banda, autor=profesor, azar=random.Random(1))
    client.force_login(profesor)
    html = client.get(reverse("clases:banda_rejilla", args=[grupo.pk])).content.decode()
    assert "{#" not in html
    assert html.count('class="casilla') == 16 * 6
    assert "T1 · ahora" in html
    assert 'id="turno-16"' in html


def test_la_rejilla_cerrada_a_otro_profesor_y_al_alumnado(client, grupo, banda, treinta):
    otro = UserFactory()
    _grupo("3-EG", otro)
    client.force_login(otro)
    assert client.get(reverse("clases:banda_rejilla", args=[grupo.pk])).status_code == 404
    assert client.post(reverse("clases:banda_generar", args=[grupo.pk])).status_code == 404
    client.force_login(treinta[0])
    assert client.get(reverse("clases:banda_rejilla", args=[grupo.pk])).status_code == 302


def test_cambiar_una_casilla_la_fija_e_intercambia(client, profesor, grupo, banda):
    bandas.generar(banda, autor=profesor, azar=random.Random(1))
    banda.refresh_from_db()
    t3 = banda.plan["turnos"][2]["alumnos"]
    client.force_login(profesor)
    url = reverse("clases:banda_casilla", args=[grupo.pk])
    client.post(url, {"turno": 3, "plaza": 0, "alumno": t3[4]})
    banda.refresh_from_db()
    nuevo = banda.plan["turnos"][2]
    assert nuevo["alumnos"][0] == t3[4] and nuevo["alumnos"][4] == t3[0]
    assert {0, 4} <= set(nuevo["fijadas"])
    client.post(url, {"turno": 3, "plaza": 0, "accion": "soltar"})
    banda.refresh_from_db()
    assert 0 not in banda.plan["turnos"][2]["fijadas"]
    client.post(url, {"turno": 3, "plaza": 1, "alumno": ""})
    banda.refresh_from_db()
    assert banda.plan["turnos"][2]["alumnos"][1] is None
    assert banda.versiones.first().origen == BandaVersion.CASILLA


def test_un_turno_jugado_no_se_cambia(client, profesor, grupo, banda, treinta):
    bandas.generar(banda, autor=profesor, azar=random.Random(1))
    for dia in range(2):
        _sesion(grupo, profesor, dia)
    banda.refresh_from_db()
    antes = banda.plan["turnos"][0]
    client.force_login(profesor)
    r = client.post(reverse("clases:banda_casilla", args=[grupo.pk]), {"turno": 1, "plaza": 0, "alumno": treinta[29].pk}, follow=True)
    assert "ya se ha jugado" in r.content.decode()
    banda.refresh_from_db()
    assert banda.plan["turnos"][0] == antes
    with pytest.raises(ValidationError):
        bandas.poner(banda, 1, 0, treinta[29].pk)


def test_configurar_cambia_las_plazas_de_lo_que_viene(client, profesor, grupo, banda):
    bandas.generar(banda, autor=profesor, azar=random.Random(1))
    client.force_login(profesor)
    datos = {
        "modo": "rotacion", "cuenta": "musica", "sesiones_por_turno": 2, "turnos": 12,
        "empieza": "2026-09-14", "plazas_bateria": 1, "plazas_ukebajo": 1, "plazas_teclado": 2,
        "plazas_electrica": 1, "plazas_espanola": 1,
    }
    r = client.post(reverse("clases:banda_configurar", args=[grupo.pk]), datos)
    assert r.status_code == 302
    banda.refresh_from_db()
    assert banda.turnos == 12 and len(banda.plan["turnos"]) == 12
    assert banda.plan["turnos"][0]["plazas"] == ["bateria", "ukebajo", "teclado", "teclado", "electrica", "espanola"]
    assert all(a is not None for a in banda.plan["turnos"][0]["alumnos"])  # se regeneró
    assert banda.versiones.first().origen == BandaVersion.CONFIGURAR


def test_el_curso_no_puede_tener_menos_turnos_que_los_jugados(banda, grupo, profesor):
    for dia in range(5):
        _sesion(grupo, profesor, dia)
    with pytest.raises(ValidationError):
        bandas.configurar(
            banda, modo=banda.modo, puestos=banda.puestos, sesiones_por_turno=2, turnos=1,
            empieza=banda.empieza, cuenta=banda.cuenta,
        )


# === C621 — la hoja para la pared ===


def test_la_hoja_trae_reglas_tabla_y_la_lista_de_cada_uno(client, profesor, grupo, banda, treinta):
    bandas.generar(banda, autor=profesor, azar=random.Random(1))
    client.force_login(profesor)
    r = client.get(reverse("clases:banda_hoja", args=[grupo.pk]))
    html = r.content.decode()
    assert r.status_code == 200
    assert "{#" not in html
    assert "Todos pasáis por la banda antes de que nadie repita" in html
    assert "size: A4 landscape" in html
    assert html.count("<tr>") == 1 + 16
    for a in treinta:
        assert bandas.nombre_de(a) in html
    assert "Tus turnos" in html


def test_la_hoja_de_4_dice_las_reglas_del_intercambio(client, profesor, grupo4, banda4):
    bandas.generar(banda4, autor=profesor, azar=random.Random(1))
    client.force_login(profesor)
    html = client.get(reverse("clases:banda_hoja", args=[grupo4.pk])).content.decode()
    assert "dos os cambiáis el instrumento" in html
    assert "Teclado 2" in html


# === C622 — la banda de hoy en la clase ===


def _hoy(client, sesion):
    return client.get(reverse("clases:banda_hoy", args=[sesion.pk])).json()


def test_sin_banda_lo_dice(client, profesor, grupo, treinta):
    s = _sesion(grupo, profesor, 0, cerrada=False)
    client.force_login(profesor)
    d = _hoy(client, s)
    assert d["hay_banda"] is False
    assert d["url_rejilla"] == reverse("clases:banda_rejilla", args=[grupo.pk])


def test_la_banda_de_hoy_dice_quien_toca_y_quien_ayuda(client, profesor, grupo, banda):
    bandas.generar(banda, autor=profesor, azar=random.Random(1))
    banda.refresh_from_db()
    for dia in range(2):
        _sesion(grupo, profesor, dia)
    hoy = _sesion(grupo, profesor, 7, cerrada=False)
    client.force_login(profesor)
    d = _hoy(client, hoy)
    assert (d["turno"], d["sesion"], d["relevo"]) == (2, 1, False)
    t1, t2 = banda.plan["turnos"][0], banda.plan["turnos"][1]
    assert [f["titular"] for f in d["filas"]] == t2["alumnos"]
    assert [f["ayuda"] for f in d["filas"]] == t1["alumnos"]
    assert d["cuenta"] is True


def test_el_ultimo_dia_del_turno_es_el_relevo(client, profesor, grupo, banda):
    bandas.generar(banda, autor=profesor, azar=random.Random(1))
    banda.refresh_from_db()
    _sesion(grupo, profesor, 0)
    hoy = _sesion(grupo, profesor, 7, cerrada=False)
    client.force_login(profesor)
    d = _hoy(client, hoy)
    assert (d["turno"], d["sesion"], d["relevo"]) == (1, 2, True)
    assert [f["entra"] for f in d["filas"]] == banda.plan["turnos"][1]["alumnos"]


def test_una_sesion_fuera_del_aula_de_musica_avisa(client, profesor, grupo, banda):
    hoy = _sesion(grupo, profesor, 0, aula="referencia", cerrada=False)
    client.force_login(profesor)
    assert _hoy(client, hoy)["cuenta"] is False


def test_la_clase_trae_el_panel_y_la_tecla_b(client, profesor, grupo, banda):
    hoy = _sesion(grupo, profesor, 0, cerrada=False)
    client.force_login(profesor)
    html = client.get(reverse("clases:class_session_present", args=[hoy.pk])).content.decode()
    assert 'id="panel-banda"' in html and 'id="fab-banda"' in html
    assert "clases/banda_hoy.js" in html
    assert "e.key === 'b'" in html
    assert "{#" not in html


def test_sin_banda_la_clase_no_trae_el_boton(client, profesor, grupo, treinta):
    hoy = _sesion(grupo, profesor, 0, cerrada=False)
    client.force_login(profesor)
    html = client.get(reverse("clases:class_session_present", args=[hoy.pk])).content.decode()
    assert 'id="fab-banda"' not in html
    assert 'id="panel-banda"' in html  # la B lo abre y dice que no hay banda


def test_el_alumnado_no_ve_la_banda_del_profesor(client, profesor, grupo, banda, treinta):
    hoy = _sesion(grupo, profesor, 0, cerrada=False)
    client.force_login(treinta[0])
    html = client.get(reverse("clases:class_session_present", args=[hoy.pk])).content.decode()
    assert 'id="panel-banda"' not in html
    assert client.get(reverse("clases:banda_hoy", args=[hoy.pk])).status_code == 302


# === C623 — ausencias y sustitutos ===


def _falta(sesion, alumno_id):
    Asistencia.objects.create(session=sesion, alumno_id=alumno_id, estado=Asistencia.FALTA)


def _sesion_del_turno_2(banda, grupo, profesor):
    bandas.generar(banda, autor=profesor, azar=random.Random(1))
    banda.refresh_from_db()
    for dia in range(2):
        _sesion(grupo, profesor, dia)
    return _sesion(grupo, profesor, 7, cerrada=False)


def test_el_sustituto_es_quien_tuvo_el_puesto_el_turno_anterior(banda, grupo, profesor):
    hoy = _sesion_del_turno_2(banda, grupo, profesor)
    t1, t2 = banda.plan["turnos"][0], banda.plan["turnos"][1]
    _falta(hoy, t2["alumnos"][0])
    d = bandas.banda_de_hoy(hoy)
    assert d["filas"][0]["falta"] is True
    assert d["filas"][0]["propuesto"] == t1["alumnos"][0]


def test_si_el_anterior_tambien_falta_entra_el_que_menos_banda_lleva(banda, grupo, profesor):
    hoy = _sesion_del_turno_2(banda, grupo, profesor)
    t1, t2 = banda.plan["turnos"][0], banda.plan["turnos"][1]
    _falta(hoy, t2["alumnos"][0])
    _falta(hoy, t1["alumnos"][0])
    d = bandas.banda_de_hoy(hoy)
    propuesto = d["filas"][0]["propuesto"]
    en_banda = {a for t in (t1, t2) for a in t["alumnos"]}
    assert propuesto is not None and propuesto not in en_banda  # nunca ha estado: cero turnos


def test_400_sorteos_nunca_proponen_a_un_ausente_ni_a_quien_ya_toca(banda, grupo, profesor, treinta):
    hoy = _sesion_del_turno_2(banda, grupo, profesor)
    ids = [a.pk for a in treinta]
    azar = random.Random(0)
    for _ in range(400):
        Asistencia.objects.filter(session=hoy).delete()
        faltan = set(azar.sample(ids, azar.randint(0, 20)))
        Asistencia.objects.bulk_create(
            [Asistencia(session=hoy, alumno_id=a, estado=Asistencia.FALTA) for a in faltan]
        )
        d = bandas.banda_de_hoy(hoy)
        tocan = {f["titular"] for f in d["filas"] if f["titular"] and not f["falta"]}
        propuestos = [f["propuesto"] for f in d["filas"] if f["propuesto"] is not None]
        assert not set(propuestos) & faltan
        assert not set(propuestos) & tocan
        assert len(propuestos) == len(set(propuestos))
        assert all(f["propuesto"] is None for f in d["filas"] if not f["falta"] and f["titular"])


def test_en_intercambio_lo_cubre_el_profesor(banda4, grupo4, profesor):
    bandas.generar(banda4, autor=profesor, azar=random.Random(1))
    banda4.refresh_from_db()
    hoy = _sesion(grupo4, profesor, 0, cerrada=False)
    _falta(hoy, banda4.plan["turnos"][0]["alumnos"][1])
    fila = bandas.banda_de_hoy(hoy)["filas"][1]
    assert fila["lo_cubre_el_profesor"] is True and fila["propuesto"] is None


def test_aceptar_y_deshacer_el_sustituto(client, banda, grupo, profesor):
    hoy = _sesion_del_turno_2(banda, grupo, profesor)
    t2 = banda.plan["turnos"][1]
    _falta(hoy, t2["alumnos"][0])
    propuesto = bandas.banda_de_hoy(hoy)["filas"][0]["propuesto"]
    client.force_login(profesor)
    url = reverse("clases:banda_hoy_cambio", args=[hoy.pk])
    r = client.post(url, json.dumps({"plaza": 0, "alumno": propuesto}), content_type="application/json")
    assert r.status_code == 200, r.content
    assert r.json()["filas"][0]["cambio"] == propuesto
    assert CambioDeHoy.objects.get(session=hoy).alumno_id == propuesto
    r = client.post(url, json.dumps({"plaza": 0, "alumno": None}), content_type="application/json")
    assert r.json()["filas"][0]["cambio"] is None
    assert not CambioDeHoy.objects.filter(session=hoy).exists()


def test_no_se_pone_a_un_ausente_ni_a_quien_ya_toca(client, banda, grupo, profesor):
    hoy = _sesion_del_turno_2(banda, grupo, profesor)
    t2 = banda.plan["turnos"][1]
    ausente = next(a.pk for a in bandas.alumnado(grupo) if a.pk not in t2["alumnos"])
    _falta(hoy, ausente)
    client.force_login(profesor)
    url = reverse("clases:banda_hoy_cambio", args=[hoy.pk])
    r = client.post(url, json.dumps({"plaza": 0, "alumno": ausente}), content_type="application/json")
    assert r.status_code == 422
    r = client.post(url, json.dumps({"plaza": 0, "alumno": t2["alumnos"][1]}), content_type="application/json")
    assert r.status_code == 422
    assert not CambioDeHoy.objects.exists()
