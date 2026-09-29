"""C337–C339: una celda vacía cuenta como 0 en la nota, y no se guarda como 0."""

from decimal import Decimal

import pytest
from django.urls import reverse

from calificaciones import calculo
from calificaciones.models import Instrumento, Nota, Plan, Prueba

D = Decimal

PESOS = {1: D(10), 2: D(20), 3: D(70)}
COMPETENCIA = {1: "CE.1", 2: "CE.1", 3: "CE.2"}
CELDAS = {(1, 1): D(10), (2, 1): D(5), (2, 2): D(15), (3, 2): D(10), (3, 3): D(60)}
MEDIA = {1: "media", 2: "media", 3: "media"}


def _alumno(pruebas, cero=True, agregaciones=MEDIA):
    return calculo.calcular_alumno(CELDAS, PESOS, COMPETENCIA, pruebas, agregaciones, cero)


# ----- la regla, en números ---------------------------------------------------


def test_hueco_cuenta_cero_hunde_la_media():
    assert calculo.nota_instrumento(calculo.rellenar([D(8), None])) == D(4)
    assert calculo.nota_instrumento([D(8), None]) == D(8)  # sin rellenar, la regla antigua


@pytest.mark.parametrize(
    "pruebas",
    [
        {1: [D(8)], 2: [None], 3: [D(6)]},
        {1: [None], 2: [None], 3: [None]},
        {1: [D(10), None], 2: [D(5)], 3: [None, None, D(9)]},
        {1: [D("7.5")], 2: [D(0)], 3: [D(10)]},
    ],
)
def test_vacio_da_lo_mismo_que_escribir_un_cero(pruebas):
    """La propiedad entera: para cualquier alumno, vacío y 0 son la misma nota."""
    con_ceros = {i: [D(0) if v is None else v for v in valores] for i, valores in pruebas.items()}
    vacio, escrito = _alumno(pruebas), _alumno(con_ceros)
    assert vacio.trimestre == escrito.trimestre
    assert vacio.simple == escrito.simple
    assert vacio.competencias == escrito.competencias
    assert vacio.instrumentos == escrito.instrumentos


def test_sin_politica_todo_sigue_igual():
    """Con la marca quitada, la cifra es la de `calcular()` de siempre."""
    pruebas = {1: [D(8)], 2: [None], 3: [D(6)]}
    antes = calculo.calcular(CELDAS, PESOS, {1: D(8), 2: None, 3: D(6)})
    ahora = _alumno(pruebas, cero=False)
    assert ahora.trimestre == antes.trimestre
    assert ahora.criterios == antes.criterios
    assert ahora.faltan == antes.faltan == 1


def test_ultima_y_mejor_no_se_hunden_por_una_columna_nueva():
    assert calculo.nota_instrumento(calculo.rellenar([D(7), None], "ultima"), "ultima") == D(7)
    assert calculo.nota_instrumento(calculo.rellenar([D(7), None], "mejor"), "mejor") == D(7)
    # Pero si no hay ninguna, el instrumento vale cero.
    assert calculo.nota_instrumento(calculo.rellenar([None, None], "ultima"), "ultima") == D(0)
    assert calculo.nota_instrumento(calculo.rellenar([None], "mejor"), "mejor") == D(0)


def test_un_instrumento_sin_pruebas_sigue_sin_nota():
    """Ocultar todas las pruebas de un instrumento lo saca de la nota, con la regla que sea."""
    r = _alumno({1: [D(8)], 2: [], 3: [D(8)]})
    assert r.instrumentos[2] is None
    assert r.trimestre == D(8)


def test_huecos_y_con_datos_cuentan_lo_escrito():
    r = _alumno({1: [D(8), None], 2: [None], 3: [D(0)]})
    assert r.huecos == 2
    assert r.con_datos is True
    nada = _alumno({1: [None], 2: [None], 3: [None]})
    assert nada.huecos == 3
    assert nada.con_datos is False
    assert nada.trimestre == D(0)


@pytest.mark.parametrize(
    "pruebas",
    [
        {1: [D(8)], 2: [D(5)], 3: [D("9.5")]},
        {1: [D(10)], 2: [None], 3: [D(3)]},
        {1: [D("6.6")], 2: [D("7.7")], 3: [D("8.8")]},
    ],
)
def test_competencias_recomponen_el_trimestre(pruebas):
    r = _alumno(pruebas)
    peso = {"CE.1": D(30), "CE.2": D(70)}
    recompuesto = sum(peso[c] * r.competencias[c] for c in peso) / D(100)
    assert abs(recompuesto - r.trimestre) <= D("0.01")


@pytest.mark.parametrize(
    ("valor", "texto"),
    [("8.35", "8.4"), ("8.34", "8.3"), ("8.25", "8.3"), ("9.95", "10.0"), ("0", "0.0"), ("4.95", "5.0")],
)
def test_un_decimal_redondea_medio_arriba(valor, texto):
    assert calculo.a_un_decimal(D(valor)) == texto
    assert calculo.a_un_decimal(None) == ""


def test_trimestre_sin_datos_no_entra_en_el_curso():
    pesos = {1: D(20), 2: D(30), 3: D(50)}
    assert calculo.nota_curso({1: D(8), 2: None, 3: None}, pesos) == D(8)
    assert calculo.nota_curso({1: D(8), 2: D(6), 3: None}, pesos) == D("6.80")


# ----- la regla, por HTTP y en la base -------------------------------------------


@pytest.mark.django_db
def test_celda_vacia_cuenta_cero_y_no_se_guarda(client, profesor, group, alumnos, plan):
    assert plan.hueco_cuenta_cero is True  # es la regla por defecto
    client.force_login(profesor)
    url = reverse("calificaciones:nota_guardar", args=[group.pk])
    teoria = Prueba.objects.get(instrumento__plan=plan, instrumento__nombre="Teoría")
    r = client.post(url, {"prueba": teoria.pk, "alumno": alumnos[0].pk, "valor": "8"})
    # Teoría pesa 30 de 100 y lo demás está vacío: 8 · 30 / 100.
    assert r.json()["trimestre"] == "2.4"
    assert r.json()["cualitativa"] == "IN"
    assert r.json()["alumno"]["trimestres"]["1"]["nota"] == "2.4"
    assert r.json()["alumno"]["trimestres"]["1"]["huecos"] == 3
    # Y en la base no hay ni un cero: solo la nota que se ha escrito.
    assert list(Nota.objects.values_list("valor", flat=True)) == [D(8)]


@pytest.mark.django_db
def test_quitar_la_marca_devuelve_la_regla_antigua_sin_tocar_notas(client, profesor, group, alumnos, plan):
    client.force_login(profesor)
    url = reverse("calificaciones:nota_guardar", args=[group.pk])
    teoria = Prueba.objects.get(instrumento__plan=plan, instrumento__nombre="Teoría")
    client.post(url, {"prueba": teoria.pk, "alumno": alumnos[0].pk, "valor": "8"})
    antes = list(Nota.objects.values_list("pk", "valor"))

    r = client.post(reverse("calificaciones:plan_ajustes", args=[plan.pk]), {})
    assert r.status_code == 302
    plan.refresh_from_db()
    assert plan.hueco_cuenta_cero is False
    assert plan.resultado_de(alumnos[0]).trimestre == D(8)
    assert list(Nota.objects.values_list("pk", "valor")) == antes

    client.post(reverse("calificaciones:plan_ajustes", args=[plan.pk]), {"hueco_cuenta_cero": "on"})
    plan.refresh_from_db()
    assert plan.resultado_de(alumnos[0]).trimestre == D("2.40")


@pytest.mark.django_db
def test_copiar_un_plan_copia_su_regla(plan):
    plan.hueco_cuenta_cero = False
    plan.save()
    assert plan.copiar(2, "copia").hueco_cuenta_cero is False


@pytest.mark.django_db
def test_una_prueba_nueva_baja_la_media_y_ocultarla_la_devuelve(profesor, alumnos, plan):
    """La consecuencia de la regla que Jesús tiene que conocer, escrita como test."""
    for instrumento in plan.instrumentos.all():
        Nota.poner(instrumento.pruebas.get(), alumnos[0], D(8), profesor)
    assert plan.resultado_de(alumnos[0]).trimestre == D(8)

    teoria = Instrumento.objects.get(plan=plan, nombre="Teoría")
    nueva = Prueba.objects.create(instrumento=teoria, nombre="Teoría 2")
    # Teoría pasa de 8 a (8 + 0) / 2 = 4, y pesa 30: 8 − 4 · 0,30 = 6,8.
    assert plan.resultado_de(alumnos[0]).trimestre == D("6.80")

    nueva.activa = False
    nueva.save()
    assert Plan.objects.get(pk=plan.pk).resultado_de(alumnos[0]).trimestre == D(8)
