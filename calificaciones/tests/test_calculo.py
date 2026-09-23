"""C212: el cuadre es una sola verdad, y un hueco no es un cero."""

from decimal import Decimal

import pytest

from calificaciones import calculo

D = Decimal

# Tres criterios (10, 20, 70) y tres instrumentos. El instrumento 1 toca dos
# criterios, el 2 uno, el 3 dos. Columnas: 1 → 15, 2 → 25, 3 → 60.
PESOS = {1: D(10), 2: D(20), 3: D(70)}
CELDAS = {(1, 1): D(10), (2, 1): D(5), (2, 2): D(15), (3, 2): D(10), (3, 3): D(60)}


def test_sin_huecos_filas_y_columnas_dan_lo_mismo():
    notas = {1: D(8), 2: D(5), 3: D("9.5")}
    por_filas = calculo.calcular(CELDAS, PESOS, notas).trimestre
    por_columnas = calculo.nota_por_columnas(CELDAS, notas)
    # A mano: 8·15 + 5·25 + 9.5·60 = 120 + 125 + 570 = 815 → 8.15
    assert por_filas == D("8.15")
    assert por_columnas == D("8.15")


@pytest.mark.parametrize(
    "notas",
    [
        {1: D(10), 2: D(0), 3: D(0)},
        {1: D("3.33"), 2: D("6.67"), 3: D("7.77")},
        {1: D(0), 2: D(10), 3: D(5)},
    ],
)
def test_igualdad_para_cualquier_conjunto_de_notas_completo(notas):
    assert calculo.calcular(CELDAS, PESOS, notas).trimestre == calculo.nota_por_columnas(CELDAS, notas)


def test_un_hueco_no_cuenta_como_cero():
    con_todo = calculo.calcular(CELDAS, PESOS, {1: D(8), 2: D(8), 3: D(8)})
    con_hueco = calculo.calcular(CELDAS, PESOS, {1: D(8), 2: None, 3: D(8)})
    assert con_todo.trimestre == D(8)
    assert con_hueco.trimestre == D(8)  # renormalizado, no hundido
    assert con_hueco.faltan == 1
    assert con_hueco.criterios[2] == D(8)  # el criterio 2 se puntúa solo con el instrumento 1


def test_sin_ninguna_nota_no_hay_nota():
    r = calculo.calcular(CELDAS, PESOS, {1: None, 2: None, 3: None})
    assert r.trimestre is None
    assert r.cualitativa == ""
    assert r.faltan == 3


def test_cero_explicito_si_cuenta():
    r = calculo.calcular(CELDAS, PESOS, {1: D(0), 2: D(10), 3: D(10)})
    # 0·15 + 10·25 + 10·60 = 850 → 8.5
    assert r.trimestre == D("8.5")


def test_criterio_sin_instrumentos_no_hunde_la_media():
    pesos = {**PESOS, 4: D(50)}  # un criterio al que ningún instrumento aporta
    r = calculo.calcular(CELDAS, pesos, {1: D(8), 2: D(8), 3: D(8)})
    assert r.trimestre == D(8)
    assert r.criterios[4] is None


def test_agregacion_de_pruebas():
    assert calculo.nota_instrumento([D(4), None, D(8)]) == D(6)
    assert calculo.nota_instrumento([D(4), None, D(8)], calculo.AGREGACION_ULTIMA) == D(8)
    assert calculo.nota_instrumento([D(9), D(4)], calculo.AGREGACION_MEJOR) == D(9)
    assert calculo.nota_instrumento([None, None]) is None


@pytest.mark.parametrize(
    "nota, esperado",
    [(D("4.99"), "IN"), (D(5), "SU"), (D("5.99"), "SU"), (D(6), "BI"), (D("6.99"), "BI"), (D(7), "NT"), (D("8.99"), "NT"), (D(9), "SB"), (D(10), "SB")],
)
def test_cualitativa(nota, esperado):
    assert calculo.cualitativa(nota) == esperado


def test_repartir_a_partes_iguales_suma_exacta():
    partes = calculo.repartir_a_partes_iguales(D(10), 3)
    assert sum(partes) == D(10)
    assert partes == [D("3.34"), D("3.33"), D("3.33")]
    assert calculo.repartir_a_partes_iguales(D(15), 2) == [D("7.5"), D("7.5")]


def test_nota_curso_pondera_trimestres():
    notas = {1: D(5), 2: D(6), 3: D(8)}
    pesos = {1: D(20), 2: D(30), 3: D(50)}
    # 100 + 180 + 400 = 680 → 6.8
    assert calculo.nota_curso(notas, pesos) == D("6.8")
    assert calculo.nota_curso({1: D(5), 2: None, 3: D(8)}, pesos) == D("7.14")


def test_si_una_fila_no_cuadra_las_dos_lecturas_divergen():
    """Por qué importa el cuadre: la lectura legal (filas) y la de clase (columnas)
    solo coinciden cuando cada fila suma exactamente el peso del criterio."""
    celdas_descuadradas = {**CELDAS, (3, 3): D(50)}  # el criterio 3 suma 60, no 70
    notas = {1: D(10), 2: D(0), 3: D(0)}
    filas = calculo.calcular(celdas_descuadradas, PESOS, notas).trimestre
    columnas = calculo.nota_por_columnas(celdas_descuadradas, notas)
    assert filas != columnas
