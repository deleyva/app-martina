"""Composición automática de un pase (C476).

Dado un grupo y una fecha, propone K preguntas activas de los conceptos que
ese grupo ha visto en sus últimas N sesiones. El orden lo deciden dos cosas:
primero el concepto más fallado por ese grupo, después la pregunta menos usada
con él. Una pregunta que ya salió a ese grupo en las últimas 3 semanas no se
repite. Si el grupo no tiene conceptos recientes, la lista vale vacía y
`motivo` lo dice: mejor eso que inventar un pase sin relación con la clase.
"""

import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta

from clases.models import ClassSession
from my_library import facets

from .models import Pase, PasePregunta, Pregunta, Respuesta

SESIONES_ATRAS = 4
SEMANAS_SIN_REPETIR = 3


def etiquetas_de_item(item):
    """Nombres de etiquetas facetadas del contenido de un elemento de sesión.

    El contenido puede ser una página con `faceted_tags` (libro, recurso,
    partitura, dictado…) o un documento/imagen cuya página de origen las tiene.
    """
    objeto = item.content_object
    if objeto is not None and hasattr(objeto, "faceted_tags"):
        return list(objeto.faceted_tags.names())
    pagina = item.get_related_scorepage()
    if pagina is not None and hasattr(pagina, "specific"):
        pagina = pagina.specific
    if pagina is not None and hasattr(pagina, "faceted_tags"):
        return list(pagina.faceted_tags.names())
    return []


def conceptos_recientes(group, fecha, sesiones_atras=SESIONES_ATRAS):
    """Conceptos (valores de `concepto:`) de las últimas N sesiones del grupo
    hasta `fecha` incluida, con cuántos elementos los llevan."""
    sesiones = ClassSession.objects.filter(group=group, date__lte=fecha).order_by(
        "-date", "-pk"
    )[:sesiones_atras]
    cuenta = Counter()
    for sesion in sesiones:
        for item in sesion.items.all():
            valores = facets.por_faceta(etiquetas_de_item(item)).get(facets.CONCEPTO, set())
            for valor in valores:
                cuenta[valor] += 1
    return cuenta


def tasa_de_fallo_por_concepto(group):
    """Para cada concepto, fallos / respuestas de ese grupo. Sin respuestas → 0."""
    respuestas = Respuesta.objects.filter(pase__group=group).select_related("pregunta")
    total, fallos = Counter(), Counter()
    for r in respuestas.prefetch_related("pregunta__etiquetas"):
        for concepto in r.pregunta.conceptos():
            total[concepto] += 1
            if not r.acierto:
                fallos[concepto] += 1
    return {c: fallos[c] / total[c] for c in total}


def veces_usada_con(group):
    cuenta = Counter()
    for pp in PasePregunta.objects.filter(pase__group=group).values_list("pregunta_id", flat=True):
        cuenta[pp] += 1
    return cuenta


def recientes_para(group, fecha, semanas=SEMANAS_SIN_REPETIR):
    desde = fecha - timedelta(weeks=semanas)
    return set(
        PasePregunta.objects.filter(
            pase__group=group, pase__fecha__gte=desde, pase__fecha__lte=fecha
        ).values_list("pregunta_id", flat=True)
    )


@dataclass
class Propuesta:
    preguntas: list = field(default_factory=list)
    conceptos: dict = field(default_factory=dict)  # concepto → tasa de fallo
    motivo: str = ""


def proponer(group, fecha, k=5, sesiones_atras=SESIONES_ATRAS, azar=random):
    conceptos = conceptos_recientes(group, fecha, sesiones_atras)
    if not conceptos:
        return Propuesta(motivo="El grupo no tiene elementos con `concepto:` en sus últimas sesiones.")

    fallo = tasa_de_fallo_por_concepto(group)
    usadas = veces_usada_con(group)
    excluidas = recientes_para(group, fecha)

    candidatas = []
    for pregunta in Pregunta.objects.filter(estado=Pregunta.ACTIVA).prefetch_related("etiquetas"):
        if pregunta.pk in excluidas:
            continue
        propios = [c for c in pregunta.conceptos() if c in conceptos]
        if not propios:
            continue
        peor = max(fallo.get(c, 0.0) for c in propios)
        candidatas.append((pregunta, peor))

    # Barajar antes de ordenar: entre iguales, el orden es al azar y no el pk.
    azar.shuffle(candidatas)
    candidatas.sort(key=lambda par: (-par[1], usadas.get(par[0].pk, 0)))

    elegidas = [p for p, _ in candidatas[:k]]
    motivo = "" if elegidas else "No hay preguntas activas de los conceptos recientes (o todas salieron hace menos de 3 semanas)."
    return Propuesta(
        preguntas=elegidas,
        conceptos={c: round(fallo.get(c, 0.0), 2) for c in conceptos},
        motivo=motivo,
    )


def crear_pase(group, fecha, preguntas, session=None, creado_por=None):
    pase = Pase.objects.create(group=group, fecha=fecha, session=session, creado_por=creado_por)
    for n, pregunta in enumerate(preguntas):
        PasePregunta.objects.create(pase=pase, pregunta=pregunta, posicion=n)
    return pase
