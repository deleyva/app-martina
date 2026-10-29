"""La casilla de Teoría acumulada (tramo 76·3): C484 a C487.

Lo que se falsa: que la casilla sea la MEDIA de los pases (no la última, no
la mejor), que los ausentes no entren en ella, que cerrar un pase no cree
columnas ni toque a nadie más, que el detalle lleve fallos y conceptos, y que
cada alumno vea solo lo suyo.
"""

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group as GrupoPermisos
from django.urls import reverse

from calificaciones import estado
from calificaciones.models import (
    CambioNota,
    Criterio,
    Instrumento,
    MarcoEvaluacion,
    Nota,
    Plan,
    Prueba,
    Reparto,
)
from clases.models import Asistencia, Enrollment, Group
from martina_bescos_app.users.permisos import GRUPO_PROFESORADO
from martina_bescos_app.users.tests.factories import UserFactory
from preguntas import teoria, vivo
from preguntas.models import Pase

from .conftest import pregunta, sesion


@pytest.fixture
def alumnos(grupo):
    us = [UserFactory(name=f"Alumno {n}") for n in ("Ana", "Bea")]
    for u in us:
        Enrollment.objects.create(user=u, group=grupo)
    return us


@pytest.fixture
def instrumento(grupo):
    """Un plan del primer trimestre con una sola columna «Teoría», numérica."""
    marco = MarcoEvaluacion.objects.create(subject=grupo.subject, nivel="3º ESO", academic_year="2026-2027")
    criterio = Criterio.objects.create(marco=marco, codigo="1.1", competencia="CE", descripcion="Criterio", peso=Decimal(100))
    plan = Plan.objects.create(marco=marco, trimestre=1, nombre="Plan teoría")
    plan.groups.add(grupo)
    instrumento = Instrumento.objects.create(plan=plan, nombre="Teoría", abreviatura="Teo")
    Reparto.objects.create(instrumento=instrumento, criterio=criterio, porcentaje=Decimal(100))
    return instrumento


@pytest.fixture
def cuatro(db):
    """Cuatro preguntas, la correcta de la i-ésima es la opción i; dos conceptos."""
    return [
        pregunta("P0 figuras", correcta=0, etiquetas=("concepto:figuras",)),
        pregunta("P1 figuras", correcta=1, etiquetas=("concepto:figuras",)),
        pregunta("P2 compás", correcta=2, etiquetas=("concepto:compas",)),
        pregunta("P3 compás", correcta=3, etiquetas=("concepto:compas",)),
    ]


def _pase(grupo, fecha, preguntas, lecturas, profesor, instrumento=None):
    """Un pase cerrado con `lecturas` = {alumno: [opción por pregunta o None]}."""
    s = sesion(grupo, fecha)
    pase, item = vivo.crear_desde_sesion(s, preguntas, profesor)
    if instrumento is not None:
        item.instrumento = instrumento
        item.save(update_fields=["instrumento"])
    vivo.abrir(pase)
    for i, pp in enumerate(pase.orden.order_by("posicion")):
        pp.lecturas = {str(a.pk): ops[i] for a, ops in lecturas.items() if ops[i] is not None}
        pp.save(update_fields=["lecturas"])
    return teoria.cerrar_y_calificar(pase, profesor)


# =============================================================================
# C484 — La casilla es la media de los pases
# =============================================================================


@pytest.mark.django_db
class TestCasilla:
    def test_la_casilla_es_la_media_y_el_detalle_lleva_fallos_y_conceptos(self, grupo, hoy, alumnos, cuatro, profesor, instrumento):
        ana, bea = alumnos
        pruebas, notas = Prueba.objects.count(), Nota.objects.count()
        d = hoy.replace(day=1)
        # Ana: 10, 5 y 7,5 → 7,5 → NT. Bea: 0 en los tres.
        _pase(grupo, d, cuatro, {ana: [0, 1, 2, 3], bea: [1, 0, 0, 0]}, profesor, instrumento)
        _pase(grupo, d.replace(day=8), cuatro, {ana: [0, 1, None, None], bea: [None] * 4}, profesor, instrumento)
        pase, escritas, aviso = _pase(grupo, d.replace(day=15), cuatro, {ana: [0, 1, 2, 0], bea: [3, 3, 3, 0]}, profesor, instrumento)

        assert (escritas, aviso) == (2, None)
        nota = Nota.objects.get(prueba__instrumento=instrumento, alumno=ana)
        assert nota.valor == Decimal("7.50")
        acumulado = nota.rubrica["acumulado"]
        assert acumulado["tipo"] == "teoria" and acumulado["n"] == 3
        assert acumulado["media"] == "7.50" and acumulado["letra"] == "NT"
        assert [r["letra"] for r in acumulado["revisiones"]] == ["SB", "SU", "NT"]
        assert [r["nota"] for r in acumulado["revisiones"]] == ["10", "5", "7,5"]
        assert acumulado["revisiones"][1]["comentario"] == "2 de 4 · 5"
        fallos = acumulado["revisiones"][1]["fallos"]
        assert [(f["enunciado"], f["sin_lectura"]) for f in fallos] == [("P2 compás", True), ("P3 compás", True)]
        assert fallos[0]["conceptos"] == ["compas"]
        # Por concepto, el peor primero: compás 3 de 6, figuras 6 de 6.
        assert acumulado["conceptos"] == [
            {"concepto": "compas", "aciertos": 3, "total": 6},
            {"concepto": "figuras", "aciertos": 6, "total": 6},
        ]
        assert Nota.objects.get(prueba__instrumento=instrumento, alumno=bea).valor == Decimal("0.00")

        # Ni una columna nueva; una nota por alumno; queda historial.
        assert Prueba.objects.count() == pruebas
        assert Nota.objects.count() == notas + 2
        # 10, luego media 7,5, luego media 7,5 otra vez: el tercer cierre no cambia el valor y no deja cambio.
        assert [c.despues for c in CambioNota.objects.filter(nota=nota).order_by("ts", "pk")] == ["10", "7.5"]

    def test_el_historial_solo_guarda_cambios_de_valor(self, grupo, hoy, alumnos, cuatro, profesor, instrumento):
        ana, bea = alumnos
        d = hoy.replace(day=1)
        _pase(grupo, d, cuatro, {ana: [0, 1, 2, 3]}, profesor, instrumento)  # 10
        _pase(grupo, d.replace(day=8), cuatro, {ana: [0, 1, 2, 3]}, profesor, instrumento)  # media 10, sin cambio
        _pase(grupo, d.replace(day=15), cuatro, {ana: [0, 1, 2, 2]}, profesor, instrumento)  # media 9,17
        nota = Nota.objects.get(prueba__instrumento=instrumento, alumno=ana)
        assert nota.valor == Decimal("9.17")
        assert [c.despues for c in CambioNota.objects.filter(nota=nota).order_by("ts", "pk")] == ["10", "9.17"]

    def test_los_ausentes_no_entran_en_su_media(self, grupo, hoy, alumnos, cuatro, profesor, instrumento):
        ana, bea = alumnos
        d = hoy.replace(day=1)
        _pase(grupo, d, cuatro, {ana: [0, 1, 2, 3], bea: [0, 1, 2, 3]}, profesor, instrumento)
        s = sesion(grupo, d.replace(day=8))
        Asistencia.objects.create(session=s, alumno=bea, estado=Asistencia.FALTA)
        pase, item = vivo.crear_desde_sesion(s, cuatro, profesor)
        item.instrumento = instrumento
        item.save(update_fields=["instrumento"])
        vivo.abrir(pase)
        for pp in pase.orden.all():
            pp.lecturas = {str(ana.pk): 0}
            pp.save(update_fields=["lecturas"])
        _, escritas, _ = teoria.cerrar_y_calificar(pase, profesor)
        assert escritas == 1  # solo Ana estaba
        assert Nota.objects.get(prueba__instrumento=instrumento, alumno=ana).valor == Decimal("6.25")  # (10 + 2,5) / 2
        assert Nota.objects.get(prueba__instrumento=instrumento, alumno=bea).valor == Decimal("10.00")
        assert Nota.objects.get(prueba__instrumento=instrumento, alumno=bea).rubrica["acumulado"]["n"] == 1

    def test_sin_instrumento_el_pase_cierra_sin_tocar_el_registro(self, grupo, hoy, alumnos, cuatro, profesor, instrumento):
        ana, bea = alumnos
        pase, escritas, aviso = _pase(grupo, hoy, cuatro, {ana: [0, 1, 2, 3]}, profesor)
        assert pase.estado == Pase.CERRADO and pase.respuestas.count() == 8
        assert (escritas, aviso) == (0, None)
        assert Nota.objects.count() == 0

    def test_con_escala_de_opciones_entra_el_valor_de_la_letra(self, grupo, hoy, alumnos, cuatro, profesor, instrumento):
        from calificaciones.plantillas import ESCALA

        instrumento.escala = Instrumento.ESCALA_OPCIONES
        instrumento.opciones = [dict(o) for o in ESCALA]
        instrumento.save()
        ana, bea = alumnos
        _pase(grupo, hoy, cuatro, {ana: [0, 1, 2, 0]}, profesor, instrumento)  # 7,5 → NT → 8
        nota = Nota.objects.get(prueba__instrumento=instrumento, alumno=ana)
        assert nota.valor == Decimal("8.00") and nota.rubrica["letra"] == "NT"

    def test_sin_columna_activa_las_respuestas_se_guardan_y_se_avisa(self, grupo, hoy, alumnos, cuatro, profesor, instrumento):
        instrumento.pruebas.update(activa=False)
        ana, bea = alumnos
        pase, escritas, aviso = _pase(grupo, hoy, cuatro, {ana: [0, 1, 2, 3]}, profesor, instrumento)
        assert pase.estado == Pase.CERRADO and pase.respuestas.count() == 8
        assert escritas == 0 and "columna" in aviso

    # C485 — el registro lleva el detalle en la celda
    def test_el_detalle_sale_en_el_estado_del_registro(self, grupo, hoy, alumnos, cuatro, profesor, instrumento):
        ana, bea = alumnos
        _pase(grupo, hoy, cuatro, {ana: [0, 1, 2, 3]}, profesor, instrumento)
        prueba = instrumento.prueba_para_evaluar()
        celda = estado.bloque_alumno(grupo, ana)["trimestres"]["1"]["notas"][str(prueba.pk)]
        assert celda["valor"] == "10" and celda["detalle"]["tipo"] == "teoria"
        assert celda["detalle"]["revisiones"][0]["fallos"] == []
        # Bea estaba y no levantó tarjeta: 0 (decisión de Jesús), con su detalle.
        celda_bea = estado.bloque_alumno(grupo, bea)["trimestres"]["1"]["notas"][str(prueba.pk)]
        assert celda_bea["valor"] == "0" and celda_bea["detalle"]["letra"] == "IN"
        assert all(f["sin_lectura"] for f in celda_bea["detalle"]["revisiones"][0]["fallos"])


# =============================================================================
# C486, C487 — Por grupo, por alumno, permisos
# =============================================================================


def _otro_profesor():
    otro = UserFactory(name="Profe Ajeno")
    otro.groups.add(GrupoPermisos.objects.get_or_create(name=GRUPO_PROFESORADO)[0])
    return otro


@pytest.mark.django_db
class TestVistas:
    def test_cerrar_por_http_califica_y_lo_dice(self, client, grupo, hoy, alumnos, cuatro, profesor, instrumento):
        ana, bea = alumnos
        s = sesion(grupo, hoy)
        pase, item = vivo.crear_desde_sesion(s, cuatro, profesor)
        item.instrumento = instrumento
        item.save(update_fields=["instrumento"])
        vivo.abrir(pase)
        for pp in pase.orden.all():
            pp.lecturas = {str(ana.pk): pp.pregunta.correcta}
            pp.save(update_fields=["lecturas"])
        client.force_login(profesor)
        r = client.post(reverse("preguntas:pase_cerrar", args=[pase.pk]))
        assert r.status_code == 200
        assert r.json()["respuestas"] == 8 and r.json()["notas"] == 2 and r.json()["aviso"] is None
        assert Nota.objects.get(prueba__instrumento=instrumento, alumno=ana).valor == Decimal("10.00")

    def test_el_resumen_del_grupo_ordena_lo_peor_primero(self, client, grupo, hoy, alumnos, cuatro, profesor, instrumento):
        ana, bea = alumnos
        _pase(grupo, hoy, cuatro, {ana: [0, 1, 0, 0], bea: [0, 0, 0, 0]}, profesor, instrumento)
        resumen = teoria.resumen_del_grupo(grupo)
        assert [(c["concepto"], c["aciertos"], c["total"]) for c in resumen["conceptos"]] == [("compas", 0, 4), ("figuras", 3, 4)]
        assert [f["pregunta"].enunciado for f in resumen["preguntas"]][:2] == ["P2 compás", "P3 compás"]
        assert resumen["preguntas"][0]["porcentaje"] == 0 and resumen["preguntas"][-1]["porcentaje"] == 100
        assert resumen["pases"][0]["media"] == "3,75" and resumen["pases"][0]["n_alumnos"] == 2  # (5 + 2,5) / 2
        assert resumen["pases"][0]["instrumento"] == instrumento

        client.force_login(profesor)
        r = client.get(reverse("preguntas:teoria_grupo", args=[grupo.pk]))
        assert r.status_code == 200
        html = r.content.decode()
        assert "concepto:compas" in html and "P2 compás" in html
        assert reverse("preguntas:editar", args=[cuatro[2].pk]) in html
        assert reverse("preguntas:teoria_alumno", args=[grupo.pk, ana.pk]) in html

    def test_permisos_del_grupo_y_del_alumno(self, client, grupo, hoy, alumnos, cuatro, profesor, instrumento):
        ana, bea = alumnos
        _pase(grupo, hoy, cuatro, {ana: [0, 1, 2, 3], bea: [0, 0, 0, 0]}, profesor, instrumento)
        url_grupo = reverse("preguntas:teoria_grupo", args=[grupo.pk])
        url_ana = reverse("preguntas:teoria_alumno", args=[grupo.pk, ana.pk])
        url_bea = reverse("preguntas:teoria_alumno", args=[grupo.pk, bea.pk])

        client.force_login(profesor)
        assert client.get(url_ana).status_code == 200
        assert "✗ P1 figuras" not in client.get(url_ana).content.decode()  # Ana no falló nada
        assert "✗ P1 figuras" in client.get(url_bea).content.decode()

        client.force_login(_otro_profesor())  # grupo ajeno → 404, no 403
        assert client.get(url_grupo).status_code == 404
        assert client.get(url_ana).status_code == 404

        client.force_login(ana)  # solo lo suyo
        assert client.get(url_ana).status_code == 200
        assert client.get(url_bea).status_code == 403
        assert client.get(url_grupo).status_code == 302  # el resumen del grupo es de profesorado

        otro_grupo = Group.objects.create(name="3º ESO Y", subject=grupo.subject, academic_year="2026-2027")
        fuera = UserFactory(name="Alumno Fuera")
        Enrollment.objects.create(user=fuera, group=otro_grupo)
        client.force_login(fuera)
        assert client.get(url_ana).status_code == 403
        assert client.get(reverse("preguntas:teoria_alumno", args=[grupo.pk, fuera.pk])).status_code == 403
