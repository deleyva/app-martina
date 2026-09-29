"""C326–C333: empezar a calificar desde una plantilla, o siguiendo con lo de la evaluación anterior."""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.management import call_command
from django.urls import reverse

from calificaciones import plantillas
from calificaciones.models import Instrumento, MarcoEvaluacion, Nota, Plan, Prueba
from clases.models import Group

D = Decimal


@pytest.fixture
def marcos(subject):
    call_command("cargar_marcos_musica", curso="2026-2027")
    return {(m.nivel, m.modalidad): m for m in MarcoEvaluacion.objects.all()}


def _adoptar(client, group, trimestre, **datos):
    return client.post(reverse("calificaciones:plan_adoptar", args=[group.pk]) + f"?t={trimestre}", datos)


# ----- las plantillas (C326, C327) ---------------------------------------------


@pytest.mark.django_db
def test_hay_una_plantilla_por_marco_y_todas_cuadran(marcos):
    assert {(p.nivel, p.modalidad) for p in plantillas.PLANTILLAS} == set(marcos)
    for plantilla in plantillas.PLANTILLAS:
        marco = marcos[(plantilla.nivel, plantilla.modalidad)]
        for trimestre in (1, 2, 3):
            plan = plantilla.crear_plan(marco, trimestre, f"{plantilla.clave} {trimestre}")
            cuadre = plan.cuadre()
            assert cuadre["cuadra"] is True, f"{plantilla.clave}: {cuadre['total']}"
            assert cuadre["total"] == D(100)
            assert [r["peso"] for r in plan.resumen()] == [r["peso"] for r in plantilla.resumen()]
            assert plan.instrumentos.count() == 9
            assert not plan.groups.exists()


@pytest.mark.django_db
def test_una_celda_cambiada_descuadra(marcos):
    """El test de arriba puede fallar: basta mover cinco puntos de un criterio a otro."""
    buena = plantillas.POR_CLAVE["3eso"]
    reparto = {**buena.reparto, "Cuaderno": {"4.1": 10}}
    mala = replace(buena, reparto=reparto)
    plan = mala.crear_plan(marcos[("3º ESO", "")], 1, "descuadrado")
    assert plan.cuadre()["cuadra"] is False
    assert plan.cuadre()["total"] == D(100)  # suma 100 y aun así no vale: falla por filas


def test_no_hay_dos_tablas_de_reparto():
    siembra = Path(__file__).parents[1] / "management" / "commands" / "cargar_marcos_musica.py"
    assert "REPARTO_" not in siembra.read_text()
    assert "INSTRUMENTOS" not in siembra.read_text()


@pytest.mark.django_db
def test_una_plantilla_sin_sus_criterios_no_se_ofrece(marcos, group):
    marcos[("3º ESO", "")].criterios.filter(codigo="4.2").delete()
    assert plantillas.POR_CLAVE["3eso"].marco_de(group) is None
    assert plantillas.empezar(group, 1, "3eso") is None
    claves = [o["plantilla"].clave for o in plantillas.opciones_para_empezar(group, 1)["plantillas"]]
    assert "3eso" not in claves


# ----- empezar con un clic (C328, C330, C333, Anti-C) --------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("trimestre", [1, 2, 3])
def test_empezar_por_plantilla_crea_un_plan_propio(client, profesor, group, marcos, trimestre):
    client.force_login(profesor)
    r = _adoptar(client, group, trimestre, plantilla="3eso")
    assert r.status_code == 302
    assert r["Location"] == f"/calificaciones/grupo/{group.pk}/?t={trimestre}"
    plan = Plan.para_grupo(group, trimestre)
    assert plan.trimestre == trimestre
    assert list(plan.groups.all()) == [group]
    assert plan.cuadre()["cuadra"] is True
    assert plan.instrumentos.filter(nombre="Sensorialidad").exists()
    assert Prueba.objects.filter(instrumento__plan=plan).count() == 9
    # Y el registro ya está para escribir.
    bloque = client.get(reverse("calificaciones:estado", args=[group.pk])).json()["trimestres"][str(trimestre)]
    assert "Sensor." in [c["corto"] for c in bloque["columnas"]]
    assert bloque["empezar"] is None


@pytest.mark.django_db
def test_dos_grupos_con_la_misma_plantilla_no_comparten_plan(client, profesor, group, subject, marcos):
    otro = Group.objects.create(name="3º ESO U", subject=subject, academic_year="2026-2027")
    otro.teachers.add(profesor)
    client.force_login(profesor)
    _adoptar(client, group, 1, plantilla="3eso")
    _adoptar(client, otro, 1, plantilla="3eso")
    assert Plan.para_grupo(group, 1).pk != Plan.para_grupo(otro, 1).pk
    assert Plan.para_grupo(group, 1).groups.count() == 1


@pytest.mark.django_db
def test_la_pantalla_sin_plan_ensena_lo_que_trae_cada_plantilla(client, profesor, group, marcos):
    client.force_login(profesor)
    empezar = client.get(reverse("calificaciones:estado", args=[group.pk])).json()["trimestres"]["1"]["empezar"]
    ofrecidas = empezar["plantillas"]
    assert [o["clave"] for o in ofrecidas][0] == "3eso"  # «3º ESO T», en castellano
    assert [o["recomendada"] for o in ofrecidas] == [True, False, False]
    assert ofrecidas[0]["nombre"] == "3º ESO"
    resumen = {r["nombre"]: r["peso"] for r in ofrecidas[0]["resumen"]}
    assert resumen["Sensorialidad"] == "10"
    assert resumen["Teoría"] == "15"
    assert empezar["anterior"] is None


@pytest.mark.django_db
def test_otro_profesor_no_empieza_en_grupo_ajeno(client, otro_profesor, otro_group, group, marcos):
    client.force_login(otro_profesor)
    assert _adoptar(client, group, 1, plantilla="3eso").status_code == 404
    assert Plan.para_grupo(group, 1) is None


@pytest.mark.django_db
def test_plantilla_que_no_existe_es_404(client, profesor, group, marcos):
    client.force_login(profesor)
    assert _adoptar(client, group, 1, plantilla="no-existe").status_code == 404
    assert Plan.para_grupo(group, 1) is None


@pytest.mark.django_db
def test_con_plan_ya_puesto_la_plantilla_no_lo_pisa(client, profesor, group, alumnos, plan, marcos):
    client.force_login(profesor)
    Nota.poner(Prueba.objects.filter(instrumento__plan=plan).first(), alumnos[0], D(7), profesor)
    _adoptar(client, group, 1, plantilla="3eso")
    assert Plan.para_grupo(group, 1).pk == plan.pk
    assert plan.instrumentos.count() == 4
    assert Nota.objects.filter(prueba__instrumento__plan=plan).count() == 1


# ----- seguir con lo mismo (C329) ----------------------------------------------


@pytest.mark.django_db
def test_la_siguiente_evaluacion_ofrece_seguir_con_lo_mismo(client, profesor, group, alumnos, plan):
    client.force_login(profesor)
    Nota.poner(Prueba.objects.filter(instrumento__plan=plan).first(), alumnos[0], D(7), profesor)
    empezar = client.get(reverse("calificaciones:estado", args=[group.pk])).json()["trimestres"]["2"]["empezar"]
    assert empezar["anterior"]["id"] == plan.pk
    assert empezar["anterior"]["trimestre"] == 1
    assert {"nombre": "Lectura rítmica", "peso": "20"} in empezar["anterior"]["resumen"]
    # Habiendo una evaluación anterior, la recomendada es seguir con lo mismo.
    assert not any(o["recomendada"] for o in empezar["plantillas"])

    assert _adoptar(client, group, 2, copiar_de=plan.pk).status_code == 302
    segundo = Plan.para_grupo(group, 2)
    assert segundo.pk != plan.pk
    assert list(segundo.groups.all()) == [group]
    assert [r for r in segundo.resumen()] == [r for r in plan.resumen()]
    assert Nota.objects.filter(prueba__instrumento__plan=segundo).count() == 0
    assert Nota.objects.filter(prueba__instrumento__plan=plan).count() == 1


@pytest.mark.django_db
def test_plan_anterior_mira_primero_hacia_atras(group, marco):
    primero = Plan.objects.create(marco=marco, trimestre=1, nombre="1")
    tercero = Plan.objects.create(marco=marco, trimestre=3, nombre="3")
    assert plantillas.plan_anterior(group, 2) is None
    tercero.groups.add(group)
    assert plantillas.plan_anterior(group, 2) == tercero
    assert plantillas.plan_anterior(group, 3) is None
    primero.groups.add(group)
    assert plantillas.plan_anterior(group, 2) == primero
    assert plantillas.plan_anterior(group, 3) == primero
    assert plantillas.plan_anterior(group, 1) == tercero


# ----- la página del plan (C332) ------------------------------------------------


@pytest.mark.django_db
def test_el_plan_dice_primero_lo_que_cuenta_cada_instrumento(client, profesor, group, plan):
    client.force_login(profesor)
    url = reverse("calificaciones:plan", args=[plan.pk])
    html = client.get(url).content.decode()
    assert "{#" not in html
    assert html.index("Lo que cuenta cada instrumento") < html.index('id="cuadre"')
    assert "Teoría <strong>30 %</strong>" in html
    assert '<details class="mb-4" id="rejilla" >' in html  # cuadra: plegada

    Instrumento.objects.get(plan=plan, nombre="Teoría").repartos.first().delete()
    html = client.get(url).content.decode()
    assert '<details class="mb-4" id="rejilla" open>' in html  # no cuadra: abierta
    assert "el reparto no coincide con la programación" in html
