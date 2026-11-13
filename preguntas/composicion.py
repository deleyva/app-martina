"""Composición automática de un pase (C476, rehecha en la fase 107).

Dado un grupo y una fecha, propone K preguntas activas de lo que ese grupo ha
visto, en su lengua. Tres reglas deciden qué puede entrar:

- **Lengua.** La de la pregunta (`idioma:en`; sin etiqueta, castellano) tiene
  que ser la del grupo (`Group.idioma`).
- **Ancla.** Una pregunta anclada a un elemento del material entra solo si el
  grupo ha visto ESE elemento: marcado visto o tratado en una clase, o dado
  por visto en el libro. La etiqueta `concepto:` es de la unidad entera y no
  distingue por dónde va el grupo dentro de ella; el ancla sí.
- **Sin ancla, por concepto.** Entra si alguno de sus conceptos ha salido en
  alguna sesión del grupo. Antes solo contaban las últimas 4; ahora, todas.

El orden: lo visto hace poco (media vida de tres semanas) más lo que el grupo
falla; a igualdad, la pregunta menos usada con él. Una pregunta que ya salió a
ese grupo en las últimas 3 semanas no se repite. Si hay preguntas de
vocabulario entre las candidatas, una de las K lo es.

Una pregunta **huérfana** —tiene ancla, pero el elemento ya no existe o ya no
está en el material de su página— no entra en ningún pase: `huerfanas()` las
lista para volver a anclarlas.
"""

import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Q

from clases.models import ClassSession, ClassSessionItem, GroupBookItem
from my_library import facets

from .models import Pase, PasePregunta, Pregunta, Respuesta

SEMANAS_SIN_REPETIR = 3
MEDIA_VIDA_DIAS = 21
# Lo dado por visto en el libro sin una clase que diga cuándo: cuenta como
# visto hace dos medias vidas, ni recién dado ni olvidado.
RECIENTE_SIN_FECHA = 0.25


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


def conceptos_vistos(group, fecha):
    """{concepto: fecha de la última sesión del grupo que lo llevó}, hasta `fecha`."""
    sesiones = ClassSession.objects.filter(group=group, date__lte=fecha).order_by("date", "pk")
    ultimo = {}
    for sesion in sesiones.prefetch_related("items"):
        for item in sesion.items.all():
            valores = facets.por_faceta(etiquetas_de_item(item)).get(facets.CONCEPTO, set())
            for valor in valores:
                ultimo[valor] = sesion.date
    return ultimo


def conceptos_recientes(group, fecha, sesiones_atras=None):
    """Compatibilidad: los conceptos vistos, como contador."""
    return Counter(conceptos_vistos(group, fecha).keys())


def elementos_vistos(group, fecha):
    """{(content_type_id, object_id): fecha en que el grupo lo vio por última vez}.

    La fecha es None cuando solo consta en el libro («visto», sin clase).
    Es la misma verdad que la barra «33 de 113»: lo marcado en clase y lo dado
    por visto en el libro. Estar en una sesión sin marcar NO cuenta: al
    preparar se mete más material del que da tiempo a dar.
    """
    vistos = {}
    en_clase = ClassSessionItem.objects.filter(
        session__group=group, session__date__lte=fecha
    ).filter(Q(visto=True) | Q(tratado=True))
    for tipo, objeto, dia in en_clase.values_list("content_type_id", "object_id", "session__date"):
        clave = (tipo, objeto)
        if vistos.get(clave) is None or dia > vistos[clave]:
            vistos[clave] = dia
    del_libro = GroupBookItem.objects.filter(
        group_book__group=group, estado__in=[GroupBookItem.VISTO, GroupBookItem.REPETIR]
    )
    for tipo, objeto in del_libro.values_list("content_type_id", "object_id"):
        vistos.setdefault((tipo, objeto), None)
    return vistos


def _material_de_pagina(pagina):
    """Claves `(content_type_id, object_id)` del material de una página.

    Vale para un capítulo y para un libro entero (un libro de recortes no
    tiene capítulos con material: sus capítulos SON el material).
    """
    from django.contrib.contenttypes.models import ContentType

    from my_library.libros import material_de, material_del_libro

    especifica = pagina.specific
    if callable(getattr(especifica, "paginas_referenciadas", None)):
        objetos = [objeto for _, objeto in material_del_libro(especifica)]
    else:
        objetos = material_de(especifica)
    return {(ContentType.objects.get_for_model(o.__class__).pk, o.pk) for o in objetos}


class _Anclas:
    """¿Sigue esta ancla en su sitio? Con caché por página: un pase mira
    decenas de preguntas de la misma unidad."""

    def __init__(self):
        self._por_pagina = {}

    def en_su_sitio(self, pregunta):
        if not pregunta.anclada:
            return True
        if pregunta.ancla_tipo_id is None or pregunta.ancla_pagina_id is None:
            return False
        if pregunta.ancla_pagina_id not in self._por_pagina:
            pagina = pregunta.ancla_pagina
            try:
                self._por_pagina[pregunta.ancla_pagina_id] = _material_de_pagina(pagina)
            except Exception:
                self._por_pagina[pregunta.ancla_pagina_id] = set()
        return pregunta.ancla_clave in self._por_pagina[pregunta.ancla_pagina_id]


def huerfanas(consulta=None):
    """Preguntas con ancla cuyo elemento ya no está en el material de su página."""
    if consulta is None:
        consulta = Pregunta.objects.exclude(estado=Pregunta.ARCHIVADA)
    anclas = _Anclas()
    return [
        p
        for p in consulta.filter(ancla_id__isnull=False).select_related("ancla_pagina", "ancla_tipo")
        if not anclas.en_su_sitio(p)
    ]


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


def _reciente(fecha, visto_el):
    """De 1 (visto hoy) hacia 0: se parte por dos cada tres semanas."""
    if visto_el is None:
        return RECIENTE_SIN_FECHA
    dias = max(0, (fecha - visto_el).days)
    return 0.5 ** (dias / MEDIA_VIDA_DIAS)


def banco_del_grupo(group, fecha):
    """[(pregunta, visto_el)] de todo lo que este grupo puede recibir hoy:
    activas, en su lengua y de algo que ya ha visto. Sin mirar repeticiones."""
    conceptos = conceptos_vistos(group, fecha)
    vistos = elementos_vistos(group, fecha)
    anclas = _Anclas()
    lengua = getattr(group, "idioma", "es") or "es"
    salida = []
    activas = (
        Pregunta.objects.filter(estado=Pregunta.ACTIVA)
        .select_related("ancla_pagina", "ancla_tipo")
        .prefetch_related("etiquetas")
    )
    for pregunta in activas:
        if pregunta.idioma != lengua:
            continue
        if pregunta.anclada:
            if pregunta.ancla_clave not in vistos or not anclas.en_su_sitio(pregunta):
                continue
            salida.append((pregunta, vistos[pregunta.ancla_clave]))
        else:
            propios = [c for c in pregunta.conceptos() if c in conceptos]
            if not propios:
                continue
            salida.append((pregunta, max(conceptos[c] for c in propios)))
    return salida


@dataclass
class Propuesta:
    preguntas: list = field(default_factory=list)
    conceptos: dict = field(default_factory=dict)  # concepto → tasa de fallo
    motivo: str = ""
    banco: list = field(default_factory=list)  # todo lo que el grupo puede recibir


def proponer(group, fecha, k=5, sesiones_atras=None, azar=random):
    banco = banco_del_grupo(group, fecha)
    conceptos = conceptos_vistos(group, fecha)
    if not banco and not conceptos and not elementos_vistos(group, fecha):
        return Propuesta(motivo="El grupo no tiene elementos con `concepto:` ni nada marcado como visto en sus sesiones.")

    fallo = tasa_de_fallo_por_concepto(group)
    usadas = veces_usada_con(group)
    excluidas = recientes_para(group, fecha)

    candidatas = []
    for pregunta, visto_el in banco:
        if pregunta.pk in excluidas:
            continue
        peor = max((fallo.get(c, 0.0) for c in pregunta.conceptos()), default=0.0)
        candidatas.append((pregunta, round(_reciente(fecha, visto_el) + peor, 4)))

    # Barajar antes de ordenar: entre iguales, el orden es al azar y no el pk.
    azar.shuffle(candidatas)
    candidatas.sort(key=lambda par: (-par[1], usadas.get(par[0].pk, 0)))

    elegidas = [p for p, _ in candidatas[:k]]
    # Una de vocabulario, si la hay y no ha entrado sola: sustituye a la última.
    if elegidas and not any(p.es_vocabulario for p in elegidas):
        de_vocabulario = next((p for p, _ in candidatas[k:] if p.es_vocabulario), None)
        if de_vocabulario is not None:
            elegidas[-1] = de_vocabulario

    motivo = ""
    if not elegidas:
        motivo = (
            "No hay preguntas activas en la lengua del grupo sobre lo que ha visto "
            "(o todas salieron hace menos de 3 semanas)."
        )
    presentes = set(conceptos) | {c for p, _ in banco for c in p.conceptos()}
    return Propuesta(
        preguntas=elegidas,
        conceptos={c: round(fallo.get(c, 0.0), 2) for c in presentes},
        motivo=motivo,
        banco=[p for p, _ in banco],
    )


def crear_pase(group, fecha, preguntas, session=None, creado_por=None):
    pase = Pase.objects.create(group=group, fecha=fecha, session=session, creado_por=creado_por)
    for n, pregunta in enumerate(preguntas):
        PasePregunta.objects.create(pase=pase, pregunta=pregunta, posicion=n)
    return pase
