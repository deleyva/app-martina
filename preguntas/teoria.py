"""La casilla de Teoría acumulada (tramo 76·3).

Al cerrar un pase, la casilla del instrumento con que se marcó «evaluable» su
elemento pasa a ser, para cada alumno con respuestas, la media de todos sus
pases cerrados en ese instrumento; se escribe con `Nota.poner` (queda
`CambioNota`) y el detalle (pases, nota de cada uno, preguntas falladas,
acierto por concepto) va en `Nota.rubrica["acumulado"]`, que es lo que el
registro enseña al pulsar la casilla. Es el mismo patrón que el dado del
cuaderno (`calificaciones/cuaderno.py`, fase 78): una casilla por instrumento,
nunca una columna por pase, porque con «celda vacía = 0» una columna por día
daría 0 a todo el que no estuvo (decisión de la fase 62).

Los ausentes de un pase no tienen `Respuesta` (C482) y por eso no entran en su
media: no es un cero, es un pase que no se les cuenta.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from calificaciones import calculo
from calificaciones.evaluar import valor_de_letra
from calificaciones.models import Instrumento, Nota
from clases.models import ClassSessionItem

from . import vivo
from .models import Pase, Respuesta

CENTESIMA = Decimal("0.01")


# =============================================================================
# QUÉ INSTRUMENTO, QUÉ PASES
# =============================================================================


def _tipo_pase():
    return ContentType.objects.get_for_model(Pase)


def elemento_de(pase) -> ClassSessionItem | None:
    """El elemento de sesión cuyo contenido es este pase (el que lleva «evaluable»)."""
    return (
        ClassSessionItem.objects.filter(content_type=_tipo_pase(), object_id=pase.pk)
        .select_related("instrumento", "instrumento__plan")
        .first()
    )


def instrumento_de(pase) -> Instrumento | None:
    """El instrumento con que se evalúa el pase; `None` si no se marcó evaluable."""
    elemento = elemento_de(pase)
    return elemento.instrumento if elemento else None


def pases_de(alumno, instrumento: Instrumento) -> list[Pase]:
    """Los pases cerrados de ese instrumento en los que el alumno tiene respuestas, por fecha."""
    ids = ClassSessionItem.objects.filter(content_type=_tipo_pase(), instrumento=instrumento).values_list(
        "object_id", flat=True
    )
    return list(
        Pase.objects.filter(pk__in=list(ids), estado=Pase.CERRADO, respuestas__alumno=alumno)
        .distinct()
        .prefetch_related("respuestas", "orden")
        .order_by("fecha", "pk")
    )


# =============================================================================
# LA MEDIA Y SU DETALLE
# =============================================================================


def _decimal(valor) -> Decimal | None:
    return None if valor is None else Decimal(str(valor)).quantize(CENTESIMA, rounding=ROUND_HALF_UP)


def _texto(valor: Decimal | None) -> str:
    return "" if valor is None else f"{valor:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def media_de(notas: list[Decimal]) -> Decimal | None:
    if not notas:
        return None
    return (sum(notas, Decimal(0)) / Decimal(len(notas))).quantize(CENTESIMA, rounding=ROUND_HALF_UP)


def _fallos(respuestas) -> list[dict]:
    return [
        {
            "pregunta": r.pregunta_id,
            "enunciado": r.pregunta.enunciado,
            "conceptos": r.pregunta.conceptos(),
            "sin_lectura": r.opcion is None,
        }
        for r in respuestas
        if not r.acierto
    ]


def _por_concepto(respuestas) -> list[dict]:
    """Acierto por concepto, peor primero: [{concepto, aciertos, total}]."""
    cuenta = defaultdict(lambda: [0, 0])
    for r in respuestas:
        for concepto in r.pregunta.conceptos() or ["(sin concepto)"]:
            cuenta[concepto][1] += 1
            cuenta[concepto][0] += int(r.acierto)
    filas = [{"concepto": c, "aciertos": a, "total": t} for c, (a, t) in cuenta.items()]
    return sorted(filas, key=lambda f: (f["aciertos"] / f["total"], f["concepto"]))


def acumulado_de(alumno, pases: list[Pase]) -> dict:
    """Lo que el registro enseña al pulsar la casilla, con la forma de la fase 78
    (`tipo`, `n`, `media`, `letra`, `revisiones`) más lo propio de los pases:
    la nota de cada uno, sus fallos y el acierto por concepto."""
    revisiones, notas, todas = [], [], []
    for pase in pases:
        respuestas = sorted(
            (r for r in pase.respuestas.all() if r.alumno_id == alumno.pk),
            key=lambda r: r.pregunta_id,
        )
        respuestas = _con_preguntas(respuestas)
        nota = _decimal(pase.nota_de(alumno.pk))
        if nota is None:
            continue
        notas.append(nota)
        todas.extend(respuestas)
        aciertos = sum(1 for r in respuestas if r.acierto)
        revisiones.append(
            {
                "sesion": pase.session_id,
                "pase": pase.pk,
                "fecha": pase.fecha.isoformat(),
                "letra": calculo.cualitativa(nota),
                "nota": _texto(nota),
                "comentario": f"{aciertos} de {len(respuestas)} · {_texto(nota)}",
                "fallos": _fallos(respuestas),
            }
        )
    media = media_de(notas)
    return {
        "tipo": "teoria",
        "n": len(revisiones),
        "media": str(media) if media is not None else "",
        "letra": calculo.cualitativa(media),
        "revisiones": revisiones,
        "conceptos": _por_concepto(todas),
    }


def _con_preguntas(respuestas):
    """Las respuestas con su pregunta cargada de una vez (vienen del prefetch sin ella)."""
    ids = {r.pregunta_id for r in respuestas}
    if not ids:
        return respuestas
    from .models import Pregunta

    preguntas = {p.pk: p for p in Pregunta.objects.filter(pk__in=ids).prefetch_related("etiquetas")}
    for r in respuestas:
        r.pregunta = preguntas[r.pregunta_id]
    return respuestas


@transaction.atomic
def recalcular(alumno, instrumento: Instrumento, user) -> Nota | None:
    """Deja la casilla del alumno como la media de sus pases en el instrumento.

    Con escala numérica se escribe la media tal cual (7,5); con lista de
    opciones, el valor de la letra de la media en esa escala, como el cuaderno.
    Sin ningún pase con respuestas, la casilla no se toca y se devuelve `None`.
    """
    prueba = instrumento.prueba_para_evaluar()
    if prueba is None:
        raise ValueError("Este instrumento no tiene ninguna columna activa en el registro")
    pases = pases_de(alumno, instrumento)
    if not pases:
        return None
    acumulado = acumulado_de(alumno, pases)
    if not acumulado["n"]:
        return None
    media = Decimal(acumulado["media"])
    if instrumento.escala == Instrumento.ESCALA_OPCIONES:
        valor = valor_de_letra(instrumento, acumulado["letra"])
    else:
        valor = media
    nota = Nota.poner(prueba, alumno, valor, user)
    rubrica = {**(nota.rubrica or {}), "acumulado": acumulado, "letra": acumulado["letra"]}
    Nota.objects.filter(pk=nota.pk).update(rubrica=rubrica)
    nota.rubrica = rubrica
    return nota


@transaction.atomic
def cerrar_y_calificar(pase, user) -> tuple[Pase, int, str | None]:
    """Cierra el pase (C482) y, si su elemento es evaluable, recalcula la casilla
    de cada alumno con respuestas. Devuelve `(pase, notas escritas, aviso)`.

    Las respuestas se guardan pase lo que pase: si el instrumento no tiene
    columna activa, el cierre sigue y el aviso lo dice.
    """
    pase = vivo.cerrar(pase)
    instrumento = instrumento_de(pase)
    if instrumento is None:
        return pase, 0, None
    alumnos = {r.alumno for r in pase.respuestas.select_related("alumno")}
    escritas = 0
    for alumno in sorted(alumnos, key=lambda a: a.pk):
        try:
            if recalcular(alumno, instrumento, user) is not None:
                escritas += 1
        except ValueError as e:
            return pase, escritas, str(e)
    return pase, escritas, None


# =============================================================================
# LO QUE SE VE POR GRUPO Y POR ALUMNO (C485, C486)
# =============================================================================


def resumen_del_grupo(group) -> dict:
    """Pases cerrados del grupo, conceptos más fallados y preguntas con peor acierto."""
    pases = list(
        Pase.objects.filter(group=group, estado=Pase.CERRADO)
        .prefetch_related("respuestas", "orden")
        .order_by("-fecha", "-pk")
    )
    respuestas = _con_preguntas(
        list(Respuesta.objects.filter(pase__in=pases).select_related("pase"))
    )
    por_pregunta = defaultdict(lambda: [0, 0])
    for r in respuestas:
        por_pregunta[r.pregunta][1] += 1
        por_pregunta[r.pregunta][0] += int(r.acierto)
    preguntas = sorted(
        (
            {"pregunta": p, "aciertos": a, "total": t, "porcentaje": round(100 * a / t)}
            for p, (a, t) in por_pregunta.items()
        ),
        key=lambda f: (f["aciertos"] / f["total"], f["pregunta"].enunciado),
    )
    filas_pases = []
    for pase in pases:
        notas = [
            _decimal(pase.nota_de(a))
            for a in {r.alumno_id for r in pase.respuestas.all()}
        ]
        notas = [n for n in notas if n is not None]
        filas_pases.append(
            {
                "pase": pase,
                "n_preguntas": pase.n_preguntas,
                "n_alumnos": len(notas),
                "media": _texto(media_de(notas)),
                "instrumento": instrumento_de(pase),
            }
        )
    return {
        "pases": filas_pases,
        "conceptos": [
            {**c, "porcentaje": round(100 * c["aciertos"] / c["total"])} for c in _por_concepto(respuestas)
        ],
        "preguntas": preguntas,
        "n_respuestas": len(respuestas),
    }


def detalle_del_alumno(group, alumno) -> dict:
    """Todos los pases cerrados del grupo en los que el alumno tiene respuestas."""
    pases = list(
        Pase.objects.filter(group=group, estado=Pase.CERRADO, respuestas__alumno=alumno)
        .distinct()
        .prefetch_related("respuestas", "orden")
        .order_by("fecha", "pk")
    )
    return acumulado_de(alumno, pases)
