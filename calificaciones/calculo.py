"""El cálculo de la nota, sin tocar la base de datos.

**Por qué está aparte de los modelos.** Es la parte que tiene que ser
verificable con un test de diez líneas y sin fixtures: dame los pesos, dame
las notas, dime la nota. Los modelos saben de dónde salen los datos; esto
solo sabe de números.

**La idea que lo sostiene.** Se guarda una celda por (criterio, instrumento)
con un porcentaje absoluto de la nota. La suma de la columna de un
instrumento es lo que se dice en clase («la lectura rítmica cuenta un 10 %»);
la suma de la fila de un criterio es el peso legal de la programación. Con
todas las notas puestas, la nota del trimestre da lo mismo leída por filas
que por columnas: es la misma suma de productos agrupada de dos maneras.

**Qué pasa con los huecos.** Hay dos reglas, y elige el plan
(`Plan.hueco_cuenta_cero`):

- *Cuenta cero* (la de ahora, desde la fase 60): una celda vacía vale 0 en la
  nota. Es como funcionaba la SPA del curso pasado y como Jesús quiere
  calificar: lo que no se ha hecho no suma. El cero se pone aquí, al calcular;
  en la base la nota sigue vacía, así que cambiar de regla no pierde nada.
- *No cuenta* (la de la fase 39): un instrumento sin nota se sale del reparto
  y el resto se renormaliza. Nació porque el 0 por defecto hundía medias de
  alumnos que simplemente no habían hecho aún la prueba.

`calcular()` no sabe de reglas: recibe las notas por instrumento y un `None`
es un hueco que se salta. La regla se aplica antes, en `calcular_alumno()`,
rellenando.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

CERO = Decimal("0")
CENTESIMA = Decimal("0.01")
DECIMA = Decimal("0.1")

AGREGACION_MEDIA = "media"
AGREGACION_ULTIMA = "ultima"
AGREGACION_MEJOR = "mejor"


def redondear(valor: Decimal | None) -> Decimal | None:
    if valor is None:
        return None
    return valor.quantize(CENTESIMA, rounding=ROUND_HALF_UP)


def a_un_decimal(valor: Decimal | None) -> str:
    """La cifra como se enseña en pantalla: un decimal, medio hacia arriba.

    Devuelve texto y no número a propósito. 8,35 es «8.4» aquí y «8.3» con el
    `toFixed(1)` de JavaScript, que redondea sobre el binario: si la pantalla
    redondeara por su cuenta, habría dos notas.
    """
    if valor is None:
        return ""
    return str(valor.quantize(DECIMA, rounding=ROUND_HALF_UP))


def rellenar(valores: list[Decimal | None], agregacion: str = AGREGACION_MEDIA) -> list[Decimal | None]:
    """Las notas de las pruebas de un instrumento con la regla «vacío cuenta cero».

    En la media, cada hueco es un cero. En «última» y «mejor» se elige entre las
    que tienen nota, y solo si no hay ninguna el instrumento vale cero: si no,
    añadir una prueba nueva pondría a cero a todo el grupo en un instrumento
    que se queda con la última.

    Sin pruebas no hay nada que rellenar: el instrumento sigue sin nota.
    """
    if not valores:
        return []
    if agregacion == AGREGACION_MEDIA:
        return [CERO if v is None else v for v in valores]
    if all(v is None for v in valores):
        return [CERO]
    return list(valores)


def media_simple(valores: list[Decimal | None]) -> Decimal | None:
    """La media aritmética de las celdas, sin pesos. Los huecos se saltan."""
    con_nota = [v for v in valores if v is not None]
    if not con_nota:
        return None
    return redondear(sum(con_nota, CERO) / Decimal(len(con_nota)))


def nota_instrumento(
    valores: list[Decimal | None], agregacion: str = AGREGACION_MEDIA
) -> Decimal | None:
    """Reduce las notas de las pruebas de un instrumento a una sola.

    `valores` va en orden cronológico (la última prueba al final). Los nulos
    se ignoran; sin ninguna nota, el instrumento no tiene nota.
    """
    con_nota = [v for v in valores if v is not None]
    if not con_nota:
        return None
    if agregacion == AGREGACION_ULTIMA:
        return con_nota[-1]
    if agregacion == AGREGACION_MEJOR:
        return max(con_nota)
    return sum(con_nota, CERO) / Decimal(len(con_nota))


def media_ponderada(
    pesos: dict[int, Decimal], notas: dict[int, Decimal | None]
) -> tuple[Decimal | None, int]:
    """Media de `notas` ponderada por `pesos`, renormalizada sobre las que existen.

    Devuelve `(nota, faltan)`: cuántas claves con peso no tienen nota. Sin
    ninguna nota, `(None, faltan)`.
    """
    suma = CERO
    peso_total = CERO
    faltan = 0
    for clave, peso in pesos.items():
        if peso <= CERO:
            continue
        nota = notas.get(clave)
        if nota is None:
            faltan += 1
            continue
        suma += peso * nota
        peso_total += peso
    if peso_total == CERO:
        return None, faltan
    return suma / peso_total, faltan


@dataclass
class Resultado:
    """Lo que el cuadro pinta de un alumno en un trimestre."""

    instrumentos: dict[int, Decimal | None] = field(default_factory=dict)
    criterios: dict[int, Decimal | None] = field(default_factory=dict)
    trimestre: Decimal | None = None
    faltan: int = 0
    # Lo que añade `calcular_alumno` (fase 60).
    simple: Decimal | None = None
    competencias: dict[str, Decimal | None] = field(default_factory=dict)
    huecos: int = 0
    con_datos: bool = False

    @property
    def cualitativa(self) -> str:
        return cualitativa(self.trimestre)


def calcular(
    celdas: dict[tuple[int, int], Decimal],
    pesos_criterio: dict[int, Decimal],
    notas_instrumento: dict[int, Decimal | None],
) -> Resultado:
    """La nota de un alumno a partir del reparto y de sus notas por instrumento.

    - `celdas`: `{(criterio_id, instrumento_id): porcentaje}`.
    - `pesos_criterio`: `{criterio_id: peso legal}`.
    - `notas_instrumento`: `{instrumento_id: nota | None}`.

    La nota del trimestre se calcula por criterios, que es la lectura legal:
    cada criterio se puntúa con los instrumentos que le aportan (ponderados por
    su celda), y después los criterios se ponderan con su peso de la
    programación. Sin huecos, coincide con sumar columna × nota.
    """
    resultado = Resultado(instrumentos=dict(notas_instrumento))

    por_criterio: dict[int, dict[int, Decimal]] = {}
    for (criterio_id, instrumento_id), porcentaje in celdas.items():
        por_criterio.setdefault(criterio_id, {})[instrumento_id] = porcentaje

    notas_criterio: dict[int, Decimal | None] = {}
    for criterio_id in pesos_criterio:
        pesos = por_criterio.get(criterio_id, {})
        nota, _ = media_ponderada(pesos, notas_instrumento)
        notas_criterio[criterio_id] = nota
    resultado.criterios = notas_criterio

    pesos_con_reparto = {
        criterio_id: peso
        for criterio_id, peso in pesos_criterio.items()
        if por_criterio.get(criterio_id)
    }
    trimestre, _ = media_ponderada(pesos_con_reparto, notas_criterio)
    resultado.trimestre = redondear(trimestre)

    instrumentos_con_celda = {i for (_, i) in celdas}
    resultado.faltan = sum(
        1 for i in instrumentos_con_celda if notas_instrumento.get(i) is None
    )
    return resultado


def competencias(
    pesos_criterio: dict[int, Decimal],
    competencia_de: dict[int, str],
    notas_criterio: dict[int, Decimal | None],
) -> dict[str, Decimal | None]:
    """La nota de cada competencia: sus criterios, ponderados por su peso legal.

    Es la misma suma que la nota del trimestre, agrupada un nivel más arriba:
    ponderar estas notas por el peso de cada competencia devuelve el trimestre.
    """
    grupos: dict[str, dict[int, Decimal]] = {}
    for criterio_id, peso in pesos_criterio.items():
        grupos.setdefault(competencia_de.get(criterio_id, ""), {})[criterio_id] = peso
    salida = {}
    for codigo, pesos in grupos.items():
        nota, _ = media_ponderada(pesos, notas_criterio)
        salida[codigo] = redondear(nota)
    return salida


def calcular_alumno(
    celdas: dict[tuple[int, int], Decimal],
    pesos_criterio: dict[int, Decimal],
    competencia_de: dict[int, str],
    pruebas: dict[int, list[Decimal | None]],
    agregaciones: dict[int, str],
    hueco_cuenta_cero: bool,
) -> Resultado:
    """Todo lo que se enseña de un alumno en un trimestre, desde sus celdas.

    - `pruebas`: `{instrumento_id: [nota | None, …]}`, las pruebas activas en
      orden cronológico.
    - `hueco_cuenta_cero`: la regla del plan.

    `huecos` y `con_datos` se cuentan sobre lo que el profesor ha escrito, antes
    de rellenar: son hechos, no política.
    """
    todas = [v for valores in pruebas.values() for v in valores]
    huecos = sum(1 for v in todas if v is None)
    con_datos = any(v is not None for v in todas)

    if hueco_cuenta_cero:
        pruebas = {i: rellenar(valores, agregaciones.get(i, AGREGACION_MEDIA)) for i, valores in pruebas.items()}

    notas = {
        i: nota_instrumento(valores, agregaciones.get(i, AGREGACION_MEDIA))
        for i, valores in pruebas.items()
    }
    resultado = calcular(celdas, pesos_criterio, notas)
    resultado.simple = media_simple([v for valores in pruebas.values() for v in valores])
    resultado.competencias = competencias(pesos_criterio, competencia_de, resultado.criterios)
    resultado.huecos = huecos
    resultado.con_datos = con_datos
    return resultado


def nota_por_columnas(
    celdas: dict[tuple[int, int], Decimal],
    notas_instrumento: dict[int, Decimal | None],
) -> Decimal | None:
    """La misma nota leída por instrumentos: Σ columna × nota, renormalizada.

    Es lo que un alumno calcula con la lista de porcentajes que se le dio en
    clase. Con todas las notas puestas, coincide con `calcular().trimestre`.
    """
    columnas: dict[int, Decimal] = {}
    for (_, instrumento_id), porcentaje in celdas.items():
        columnas[instrumento_id] = columnas.get(instrumento_id, CERO) + porcentaje
    nota, _ = media_ponderada(columnas, notas_instrumento)
    return redondear(nota)


def nota_curso(
    notas_trimestre: dict[int, Decimal | None], pesos_trimestre: dict[int, Decimal]
) -> Decimal | None:
    nota, _ = media_ponderada(pesos_trimestre, notas_trimestre)
    return redondear(nota)


def cualitativa(nota: Decimal | None) -> str:
    """La misma escala que la hoja del departamento."""
    if nota is None:
        return ""
    if nota < 5:
        return "IN"
    if nota < 6:
        return "SU"
    if nota < 7:
        return "BI"
    if nota < 9:
        return "NT"
    return "SB"


CUALITATIVAS = {
    "IN": "Insuficiente",
    "SU": "Suficiente",
    "BI": "Bien",
    "NT": "Notable",
    "SB": "Sobresaliente",
}


def repartir_a_partes_iguales(total: Decimal, n: int) -> list[Decimal]:
    """Parte `total` en `n` trozos con dos decimales que suman exactamente `total`.

    El resto de la división se lo lleva el primero, para que 10 entre 3 sea
    3,34 + 3,33 + 3,33 y no 9,99.
    """
    if n <= 0:
        return []
    parte = (total / Decimal(n)).quantize(CENTESIMA, rounding=ROUND_HALF_UP)
    partes = [parte] * n
    partes[0] = partes[0] + (total - parte * n)
    return partes
