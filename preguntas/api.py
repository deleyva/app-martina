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


class PreguntaIn(Schema):
    enunciado: str
    opciones: List[str]
    correcta: int
    explicacion: Optional[str] = ""
    etiquetas: List[str] = []
    imagen_id: Optional[int] = None


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
            ids.append(pregunta.pk)
    return LoteOut(ids=ids, creadas=len(ids))
