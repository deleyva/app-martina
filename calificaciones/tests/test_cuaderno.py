"""Fase 78 — El dado del cuaderno. Los falsadores de C495 a C502 y los anti-claims.

Lo universal se prueba como universal: el sorteo con cientos de tiradas, no
con un ejemplo.
"""

import json
import random
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from calificaciones import cuaderno
from calificaciones.models import CambioNota, Instrumento, Nota, Prueba, RevisionCuaderno
from calificaciones.plantillas import ESCALA
from clases import plano as planos
from clases.models import ClassSession, Enrollment
from martina_bescos_app.users.tests.factories import UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("_hosts")]


@pytest.fixture
def _hosts(settings):
    settings.ALLOWED_HOSTS = ["*"]
    settings.APPS_CANDADO = False


@pytest.fixture
def cuad(plan):
    """El «Cuaderno» del plan, con la escala del curso (SB 9,5 · NT 8 · BI 6,5 · SU 5,5 · IN 4)."""
    instrumento = plan.instrumentos.get(nombre="Cuaderno")
    instrumento.escala = Instrumento.ESCALA_OPCIONES
    instrumento.opciones = [dict(o) for o in ESCALA]
    instrumento.save()
    return instrumento


def _sesion(group, profesor, dia=7):
    return ClassSession.objects.create(teacher=profesor, group=group, date=date(2026, 10, dia), title="Clase")


@pytest.fixture
def sesion(group, profesor, cuad):
    return _sesion(group, profesor)


def _post(client, nombre, sesion, cuerpo):
    return client.post(
        reverse(f"clases:{nombre}", args=[sesion.pk]), data=json.dumps(cuerpo), content_type="application/json"
    )


# =============================================================================
# C495 · una revisión por sesión y alumno
# =============================================================================


def test_una_revision_por_sesion_y_alumno(sesion, alumnos, cuad):
    RevisionCuaderno.objects.create(session=sesion, alumno=alumnos[0], instrumento=cuad)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RevisionCuaderno.objects.create(session=sesion, alumno=alumnos[0], instrumento=cuad)
    assert RevisionCuaderno.objects.get().pendiente


# =============================================================================
# C496 · el dado prefiere a los menos revisados y nunca saca a un excluido
# =============================================================================


def _revision(group, profesor, alumno, cuad, dia, letra="BI"):
    s = _sesion(group, profesor, dia)
    return RevisionCuaderno.objects.create(
        session=s, alumno=alumno, instrumento=cuad, letra=letra, valor=cuaderno.valor_de_letra(cuad, letra)
    )


def test_el_dado_saca_a_los_que_menos_veces_han_salido(group, profesor, alumnos, cuad, sesion):
    a0, a1, a2 = alumnos
    _revision(group, profesor, a0, cuad, 1)
    _revision(group, profesor, a0, cuad, 2)
    _revision(group, profesor, a1, cuad, 3)
    # Una pendiente (sin letra) de otro día no cuenta como revisión.
    RevisionCuaderno.objects.create(session=_sesion(group, profesor, 4), alumno=a2, instrumento=cuad)
    for _ in range(50):
        sesion.revisiones_cuaderno.all().delete()
        filas = cuaderno.sortear(sesion, cuad, n=2)
        assert {f.alumno_id for f in filas} == {a2.pk, a1.pk}
    sesion.revisiones_cuaderno.all().delete()
    (sola,) = cuaderno.sortear(sesion, cuad, n=1)
    assert sola.alumno_id == a2.pk


def test_400_tiradas_nunca_sacan_a_un_excluido_y_el_empate_es_al_azar(group, profesor, cuad, sesion):
    nombres = ["falta", "sin libreta", "ya salio", "saltado", "libre A", "libre B"]
    alumnos = {n: UserFactory(name=n) for n in nombres}
    for a in alumnos.values():
        Enrollment.objects.create(user=a, group=group)
    planos.marcar(sesion, alumnos["falta"].pk, estado="falta")
    planos.marcar(sesion, alumnos["sin libreta"].pk, sin_material=["libreta"])
    ya = RevisionCuaderno.objects.create(session=sesion, alumno=alumnos["ya salio"], instrumento=cuad)
    vistos = set()
    for _ in range(400):
        sesion.revisiones_cuaderno.exclude(pk=ya.pk).delete()
        (fila,) = cuaderno.sortear(sesion, cuad, n=1, excluir=[alumnos["saltado"].pk])
        vistos.add(fila.alumno.name)
    assert vistos == {"libre A", "libre B"}


def test_quien_llega_con_retraso_si_puede_salir(sesion, alumnos, cuad):
    planos.marcar(sesion, alumnos[0].pk, estado="retraso")
    planos.marcar(sesion, alumnos[1].pk, estado="falta")
    planos.marcar(sesion, alumnos[2].pk, estado="falta")
    (fila,) = cuaderno.sortear(sesion, cuad, n=2)
    assert fila.alumno_id == alumnos[0].pk


def test_sin_nadie_el_dado_no_crea_nada(sesion, alumnos, cuad):
    for a in alumnos:
        planos.marcar(sesion, a.pk, estado="falta")
    assert cuaderno.sortear(sesion, cuad) == []
    assert RevisionCuaderno.objects.count() == 0


def test_un_instrumento_de_otro_plan_se_rechaza(sesion, alumnos, otro_group, marco):
    from calificaciones.models import Plan

    ajeno = Plan.objects.create(marco=marco, trimestre=1, nombre="Ajeno")
    ajeno.groups.add(otro_group)
    instrumento = Instrumento.objects.create(plan=ajeno, nombre="Cuaderno", abreviatura="Cuad")
    with pytest.raises(ValueError, match="no es de un plan de este grupo"):
        cuaderno.sortear(sesion, instrumento)


# =============================================================================
# C504 · tope de tres al día; cerrar la franja descarta los pendientes
# =============================================================================


def test_hoy_salen_como_mucho_tres(group, profesor, cuad, sesion):
    for n in range(6):
        Enrollment.objects.create(user=UserFactory(name=f"Alumno {n}"), group=group)
    assert len(cuaderno.sortear(sesion, cuad, n=2)) == 2
    assert len(cuaderno.sortear(sesion, cuad, n=1)) == 1
    assert cuaderno.sortear(sesion, cuad, n=1) == []
    assert cuaderno.sortear(sesion, cuad, n=2) == []
    assert sesion.revisiones_cuaderno.count() == 3
    assert cuaderno.estado_de_lista(sesion)["maximo"] == 3


def test_los_calificados_cuentan_para_el_tope(group, profesor, cuad, sesion):
    for n in range(6):
        Enrollment.objects.create(user=UserFactory(name=f"Alumno {n}"), group=group)
    primera, segunda = cuaderno.sortear(sesion, cuad, n=2)
    cuaderno.calificar(sesion, primera.alumno, "BI", profesor)
    cuaderno.calificar(sesion, segunda.alumno, "NT", profesor)
    # Cerrar y volver a tirar: solo cabe uno más, y nunca uno de los dos ya mirados.
    assert cuaderno.descartar(sesion) == 0
    (tercero,) = cuaderno.sortear(sesion, cuad, n=2)
    assert tercero.alumno_id not in {primera.alumno_id, segunda.alumno_id}
    assert cuaderno.sortear(sesion, cuad, n=2) == []


def test_cerrar_descarta_los_pendientes_y_no_los_calificados(client, profesor, group, cuad, sesion):
    for n in range(6):
        Enrollment.objects.create(user=UserFactory(name=f"Alumno {n}"), group=group)
    a, b = cuaderno.sortear(sesion, cuad, n=2)
    cuaderno.calificar(sesion, a.alumno, "SB", profesor)
    client.force_login(profesor)
    r = _post(client, "cuaderno_descartar", sesion, {})
    assert r.status_code == 200
    assert [s["alumno"] for s in r.json()["sorteados"]] == [a.alumno_id]
    assert r.json()["pendientes"] == 0
    assert not RevisionCuaderno.objects.filter(pk=b.pk).exists()
    # El siguiente dado reparte de nuevo, con sitio para dos (uno mirado + dos = tres).
    r = _post(client, "cuaderno_sortear", sesion, {})
    nuevos = {s["alumno"] for s in r.json()["sorteados"]}
    assert len(nuevos) == 3 and a.alumno_id in nuevos
    assert Nota.objects.filter(alumno=a.alumno).exists()


# =============================================================================
# C498 · la casilla es la letra de la media; nada más se toca
# =============================================================================


def test_la_casilla_es_la_letra_de_la_media_de_las_revisiones(group, profesor, alumnos, cuad):
    alumno = alumnos[0]
    pruebas, notas = Prueba.objects.count(), Nota.objects.count()
    letras = []
    for dia, letra in ((1, "SB"), (2, "IN"), (3, "NT")):
        s = _sesion(group, profesor, dia)
        cuaderno.sortear(s, cuad, n=1, azar=random.Random(1))
        # Se califica a ESTE alumno aunque el dado sacara a otro: calificar admite a cualquiera del grupo.
        fila, nota = cuaderno.calificar(s, alumno, letra, profesor, comentario=f"día {dia}")
        letras.append(nota.rubrica["acumulado"]["letra"])
    # 9,5 · 4 · 8 → 7,17 → NT → 8 en la casilla.
    assert letras == ["SB", "BI", "NT"]
    nota = Nota.objects.get(prueba=cuad.prueba_para_evaluar(), alumno=alumno)
    assert nota.valor == Decimal("8")
    assert nota.rubrica["acumulado"]["n"] == 3
    assert nota.rubrica["acumulado"]["media"] == "7.17"
    assert [r["letra"] for r in nota.rubrica["acumulado"]["revisiones"]] == ["SB", "IN", "NT"]
    assert [r["comentario"] for r in nota.rubrica["acumulado"]["revisiones"]] == ["día 1", "día 2", "día 3"]
    # Ni una columna nueva, ni la nota de nadie más; y el cambio queda en el historial.
    assert Prueba.objects.count() == pruebas
    assert Nota.objects.count() == notas + 1
    assert CambioNota.objects.filter(nota=nota).count() == 3  # 9,5 → 6,5 → 8


def test_una_pendiente_no_es_nota(sesion, alumnos, cuad):
    cuaderno.sortear(sesion, cuad)
    assert Nota.objects.count() == 0
    assert cuaderno.recalcular(alumnos[0], cuad, None) is None


def test_calificar_dos_veces_el_mismo_dia_es_una_sola_revision(sesion, alumnos, cuad, profesor):
    cuaderno.calificar(sesion, alumnos[0], "IN", profesor)
    _, nota = cuaderno.calificar(sesion, alumnos[0], "SB", profesor, comentario="corregido")
    assert RevisionCuaderno.objects.filter(alumno=alumnos[0]).count() == 1
    assert nota.rubrica["acumulado"]["n"] == 1
    assert nota.valor == Decimal("9.5")


def test_saltar_borra_la_pendiente_pero_no_la_hecha(sesion, alumnos, cuad, profesor):
    cuaderno.sortear(sesion, cuad, n=2)
    hecha = sesion.revisiones_cuaderno.first()
    cuaderno.calificar(sesion, hecha.alumno, "BI", profesor)
    pendiente = sesion.revisiones_cuaderno.exclude(pk=hecha.pk).get()
    assert cuaderno.saltar(sesion, pendiente.alumno_id) is True
    assert cuaderno.saltar(sesion, hecha.alumno_id) is False
    assert list(sesion.revisiones_cuaderno.values_list("pk", flat=True)) == [hecha.pk]


@pytest.mark.parametrize("letra", ["", "A", "sb ", "X"])
def test_letras_fuera_de_la_escala_se_rechazan(sesion, alumnos, cuad, profesor, letra):
    if letra.strip().upper() == "SB":
        cuaderno.calificar(sesion, alumnos[0], letra, profesor)  # con espacios y minúsculas vale
        return
    with pytest.raises(ValueError):
        cuaderno.calificar(sesion, alumnos[0], letra, profesor)


# =============================================================================
# C500 · sin «Cuaderno» en el plan, se elige instrumento
# =============================================================================


def test_sin_cuaderno_en_el_plan_el_dado_lo_dice_y_deja_elegir(client, profesor, sesion, alumnos, cuad):
    cuad.nombre = "Libreta"
    cuad.save()
    assert cuaderno.instrumento_de(sesion) is None
    estado = cuaderno.estado_de_lista(sesion)
    assert estado["instrumento"] is None
    assert {o["nombre"] for o in estado["opciones"]} == {"Teoría", "Lectura rítmica", "Dictado", "Libreta"}
    client.force_login(profesor)
    r = _post(client, "cuaderno_sortear", sesion, {})
    assert r.status_code == 400 and "Elige" in r.json()["error"]
    r = _post(client, "cuaderno_sortear", sesion, {"instrumento": cuad.pk})
    assert r.status_code == 200
    assert r.json()["instrumento"]["nombre"] == "Libreta"
    assert len(r.json()["sorteados"]) == 2
    # La elección queda en la sesión: la segunda tirada ya no pide instrumento.
    assert cuaderno.instrumento_de(sesion) == cuad
    r = _post(client, "cuaderno_sortear", sesion, {"n": 1})
    assert r.status_code == 200 and len(r.json()["sorteados"]) == 3


def test_sin_plan_no_hay_ni_opciones(client, profesor, group, alumnos, plan):
    plan.groups.remove(group)
    s = _sesion(group, profesor)
    estado = cuaderno.estado_de_lista(s)
    assert estado["instrumento"] is None and estado["opciones"] == []
    client.force_login(profesor)
    assert _post(client, "cuaderno_sortear", s, {}).status_code == 400


def test_el_cuaderno_se_encuentra_sin_mirar_mayusculas_ni_acentos(sesion, cuad):
    cuad.nombre = "CUADERNO"
    cuad.save()
    assert cuaderno.instrumento_de(sesion) == cuad


# =============================================================================
# C499 · el sorteo persiste con el pase de lista
# =============================================================================


def test_los_datos_de_lista_llevan_el_cuaderno(client, profesor, sesion, alumnos, cuad):
    client.force_login(profesor)
    r = _post(client, "cuaderno_sortear", sesion, {})
    assert r.status_code == 200
    ids = {s["alumno"] for s in r.json()["sorteados"]}
    datos = client.get(reverse("clases:lista_datos", args=[sesion.pk])).json()
    assert {s["alumno"] for s in datos["cuaderno"]["sorteados"]} == ids
    assert datos["cuaderno"]["pendientes"] == 2
    assert datos["cuaderno"]["candidatos"] == 1
    # Calificar desde la vista: la casilla viene en la respuesta y queda en el registro.
    alumno = next(iter(ids))
    r = _post(client, "cuaderno_calificar", sesion, {"alumno": alumno, "letra": "NT", "comentario": "bien"})
    assert r.status_code == 200
    assert r.json()["guardado"] == {"alumno": alumno, "letra": "NT", "casilla": "NT"}
    assert r.json()["pendientes"] == 1
    hecho = next(s for s in r.json()["sorteados"] if s["alumno"] == alumno)
    assert hecho["casilla"] == {"letra": "NT", "n": 1, "media": "8.00"}
    # Saltar al que queda: se va y entra el único que faltaba por salir.
    otro = next(iter(ids - {alumno}))
    r = _post(client, "cuaderno_saltar", sesion, {"alumno": otro})
    assert r.status_code == 200
    nuevos = {s["alumno"] for s in r.json()["sorteados"]}
    assert otro not in nuevos and len(nuevos) == 2
    # El saltado vuelve a ser candidato (no se le marcó falta ni «sin libreta»):
    # es la pantalla quien lo recuerda y lo manda en `excluir` en cada tirada.
    assert r.json()["candidatos"] == 1
    r = _post(client, "cuaderno_sortear", sesion, {"n": 1, "excluir": [otro]})
    assert r.status_code == 200
    assert {s["alumno"] for s in r.json()["sorteados"]} == nuevos


def test_el_detalle_sale_en_el_estado_del_registro(client, profesor, group, sesion, alumnos, cuad):
    from calificaciones import estado

    cuaderno.calificar(sesion, alumnos[0], "SB", profesor, comentario="limpio")
    bloque = estado.bloque_alumno(group, alumnos[0])
    celda = bloque["trimestres"]["1"]["notas"][str(cuad.prueba_para_evaluar().pk)]
    assert celda["etiqueta"] == "SB"
    assert celda["detalle"]["n"] == 1 and celda["detalle"]["revisiones"][0]["comentario"] == "limpio"
    otra = bloque["trimestres"]["1"]["notas"][str(plan_prueba(group, "Teoría").pk)]
    assert "detalle" not in otra


def plan_prueba(group, nombre):
    return Prueba.objects.get(instrumento__nombre=nombre, instrumento__plan__groups=group)


# =============================================================================
# C502 · permisos
# =============================================================================


def test_solo_quien_da_la_sesion_tira_y_califica(client, otro_profesor, sesion, alumnos, group):
    group.teachers.add(otro_profesor)  # cotitular del grupo, pero la sesión no es suya
    client.force_login(otro_profesor)
    assert client.get(reverse("clases:cuaderno_estado", args=[sesion.pk])).status_code == 404
    assert _post(client, "cuaderno_sortear", sesion, {}).status_code == 404
    assert _post(client, "cuaderno_calificar", sesion, {"alumno": alumnos[0].pk, "letra": "SB"}).status_code == 404
    assert _post(client, "cuaderno_descartar", sesion, {}).status_code == 404
    assert RevisionCuaderno.objects.count() == 0


def test_el_alumnado_no_llega_al_dado(client, sesion, alumnos):
    client.force_login(alumnos[0])
    r = client.get(reverse("clases:cuaderno_estado", args=[sesion.pk]))
    assert r.status_code in (302, 403)
    r = _post(client, "cuaderno_sortear", sesion, {})
    assert r.status_code in (302, 403)
    assert RevisionCuaderno.objects.count() == 0


def test_alumno_ajeno_e_instrumento_ajeno_dan_400(client, profesor, sesion, alumnos, cuad, otro_group, marco):
    from calificaciones.models import Plan

    client.force_login(profesor)
    ajeno = UserFactory()
    r = _post(client, "cuaderno_calificar", sesion, {"alumno": ajeno.pk, "letra": "SB"})
    assert r.status_code == 400 and "no es de este grupo" in r.json()["error"]
    cuad.nombre = "Libreta"
    cuad.save()
    plan_ajeno = Plan.objects.create(marco=marco, trimestre=1, nombre="Ajeno")
    plan_ajeno.groups.add(otro_group)
    instrumento = Instrumento.objects.create(plan=plan_ajeno, nombre="Cuaderno", abreviatura="Cuad")
    r = _post(client, "cuaderno_sortear", sesion, {"instrumento": instrumento.pk})
    assert r.status_code == 400
    assert RevisionCuaderno.objects.count() == 0


@pytest.mark.parametrize(
    "cuerpo, vistas",
    [
        ("no json", ("cuaderno_sortear", "cuaderno_saltar", "cuaderno_calificar")),
        ("[1, 2]", ("cuaderno_sortear", "cuaderno_saltar", "cuaderno_calificar")),
        ('{"alumno": "x", "letra": "SB"}', ("cuaderno_saltar", "cuaderno_calificar")),
        ('{"n": "dos"}', ("cuaderno_sortear",)),
        ('{"excluir": "3"}', ("cuaderno_sortear",)),
        ('{"excluir": [true]}', ("cuaderno_sortear",)),
    ],
)
def test_formas_malas_dan_400_y_no_500(client, profesor, sesion, alumnos, cuad, cuerpo, vistas):
    client.force_login(profesor)
    for nombre in vistas:
        r = client.post(reverse(f"clases:{nombre}", args=[sesion.pk]), data=cuerpo, content_type="application/json")
        assert r.status_code == 400, (nombre, cuerpo, r.content)
    assert RevisionCuaderno.objects.count() == 0
