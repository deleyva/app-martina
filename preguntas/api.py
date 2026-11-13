"""`POST /api/cms/preguntas/` — alta por lote, siempre «sin revisar» (C474).

Se monta dentro del router del CMS para compartir su autenticación por API
key (`PublishIES` publica con esa clave). El lote es atómico: una pregunta
inválida tira el lote entero con un 400 que dice cuál.
"""

from typing import List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from ninja import Router, Schema
from ninja.errors import HttpError

from cms.etiquetas import facetas_desconocidas
from my_library import facets

from .models import OPCIONES, Pregunta

router = Router(tags=["Preguntas"])


class AnclaIn(Schema):
    """A qué elemento del material se ancla: la página y el elemento, dicho
    por su posición de hoy en el material (`indice`) o por `tipo` + `id`."""

    pagina_id: int
    indice: Optional[int] = None
    tipo: Optional[str] = None
    id: Optional[int] = None


class PreguntaIn(Schema):
    enunciado: str
    opciones: List[str]
    correcta: int
    explicacion: Optional[str] = ""
    etiquetas: List[str] = []
    imagen_id: Optional[int] = None
    ancla: Optional[AnclaIn] = None


class LoteIn(Schema):
    preguntas: List[PreguntaIn]


class LoteOut(Schema):
    ids: List[int]
    creadas: int


@router.post("/", response=LoteOut)
def crear_preguntas(request, payload: LoteIn):
    if not payload.preguntas:
        raise HttpError(400, "Manda al menos una pregunta.")
    ids = []
    with transaction.atomic():
        for n, datos in enumerate(payload.preguntas, start=1):
            if len(datos.opciones) != OPCIONES:
                raise HttpError(400, f"Pregunta {n}: hacen falta exactamente {OPCIONES} opciones.")
            if not 0 <= datos.correcta < OPCIONES:
                raise HttpError(400, f"Pregunta {n}: `correcta` tiene que estar entre 0 y {OPCIONES - 1}.")
            malas = facetas_desconocidas(datos.etiquetas)
            if malas:
                raise HttpError(
                    400,
                    f"Pregunta {n}: faceta desconocida en {malas}. Válidas: {', '.join(facets.FACETAS)}.",
                )
            if not any(facets.valor_de(e, facets.CONCEPTO) for e in datos.etiquetas):
                raise HttpError(400, f"Pregunta {n}: hace falta al menos una etiqueta `concepto:…`.")
            pregunta = Pregunta(
                enunciado=datos.enunciado.strip(),
                opciones=[o.strip() for o in datos.opciones],
                correcta=datos.correcta,
                explicacion=(datos.explicacion or "").strip(),
                autor=request.user if getattr(request.user, "is_authenticated", False) else None,
                imagen_id=datos.imagen_id,
                estado=Pregunta.SIN_REVISAR,
            )
            try:
                pregunta.save()
            except ValidationError as error:
                raise HttpError(400, f"Pregunta {n}: {error.messages[0]}")
            pregunta.etiquetas.set([e.strip() for e in datos.etiquetas if e.strip()])
            if datos.ancla is not None:
                _anclar(pregunta, datos.ancla, f"Pregunta {n}")
            ids.append(pregunta.pk)
    return LoteOut(ids=ids, creadas=len(ids))


# =============================================================================
# ANCLAS (fase 107)
# =============================================================================


def _anclar(pregunta, ancla: AnclaIn, quien: str):
    from wagtail.models import Page

    from . import anclas

    pagina = Page.objects.filter(pk=ancla.pagina_id).first()
    if pagina is None:
        raise HttpError(400, f"{quien}: no existe la página {ancla.pagina_id}.")
    material = anclas.material_listado(pagina)
    if ancla.indice is not None:
        elegido = next((m for m in material if m["indice"] == ancla.indice), None)
    else:
        elegido = next((m for m in material if m["tipo"] == ancla.tipo and m["id"] == ancla.id), None)
    if elegido is None:
        raise HttpError(400, f"{quien}: ese elemento no está en el material de la página {ancla.pagina_id}.")
    anclas.anclar(pregunta, pagina, elegido["tipo_id"], elegido["id"])
    return elegido


class MaterialOut(Schema):
    indice: int
    tipo: str
    id: int
    titulo: str
    clase: str


@router.get("/material/{pagina_id}", response=List[MaterialOut])
def material_de_pagina(request, pagina_id: int):
    """El material de una página (capítulo o libro), en orden, para anclar."""
    from wagtail.models import Page

    from . import anclas

    pagina = Page.objects.filter(pk=pagina_id).first()
    if pagina is None:
        raise HttpError(404, "No existe esa página.")
    return anclas.material_listado(pagina)


class AnclaDePreguntaIn(Schema):
    pregunta_id: int
    ancla: Optional[AnclaIn] = None  # None = quitar el ancla


class AnclasIn(Schema):
    anclas: List[AnclaDePreguntaIn]


class AnclasOut(Schema):
    ancladas: int
    desancladas: int


@router.post("/anclas", response=AnclasOut)
def poner_anclas(request, payload: AnclasIn):
    """Ancla (o desancla) preguntas que ya existen. Atómico, como el alta."""
    from . import anclas

    ancladas = desancladas = 0
    with transaction.atomic():
        for fila in payload.anclas:
            pregunta = Pregunta.objects.filter(pk=fila.pregunta_id).first()
            if pregunta is None:
                raise HttpError(400, f"No existe la pregunta {fila.pregunta_id}.")
            if fila.ancla is None:
                anclas.desanclar(pregunta)
                desancladas += 1
            else:
                _anclar(pregunta, fila.ancla, f"Pregunta {fila.pregunta_id}")
                ancladas += 1
    return AnclasOut(ancladas=ancladas, desancladas=desancladas)


class PreguntaOut(Schema):
    id: int
    enunciado: str
    estado: str
    etiquetas: List[str]
    anclada: bool


@router.get("/", response=List[PreguntaOut])
def listar_preguntas(request):
    """Lo mínimo para saber qué hay y qué falta por anclar."""
    return [
        PreguntaOut(
            id=p.pk,
            enunciado=p.enunciado,
            estado=p.estado,
            etiquetas=sorted(e.name for e in p.etiquetas.all()),
            anclada=p.anclada,
        )
        for p in Pregunta.objects.order_by("pk").prefetch_related("etiquetas")
    ]
