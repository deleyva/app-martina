# ruff: noqa: E501, C901, PLR0912, FBT001, FBT002  — filtros de consulta: las ramas y los booleanos son los parámetros de la URL
"""API de solo lectura de incidencias, para la skill que reparte el juego.

Todo lo que expone ya existe en el panel: la diferencia es que aquí se lee con
clave de API (cabecera `X-API-Key`) en vez de con sesión. Como el panel enseña
las incidencias privadas, la clave tiene que pertenecer a un técnico activo o a
un superusuario; cualquier otra clave válida recibe 403.

No hay escritura. Asignar, comentar, cambiar de estado o derivar a un servicio
externo llegarán con la skill, cuando se sepa qué forma tienen.
"""

from datetime import date
from datetime import datetime

from django.db.models import Count
from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja import Schema
from ninja.errors import HttpError

from api_keys.auth import DatabaseApiKey

from .models import Etiqueta
from .models import Incidencia
from .models import Tecnico
from .models import Ubicacion

router = Router(tags=["Incidencias"], auth=DatabaseApiKey())

LIMITE_MAXIMO = 500


# ---------------------------------------------------------------------------
# Permiso
# ---------------------------------------------------------------------------


def _exigir_tecnico(request):
    """La API enseña incidencias privadas: solo técnicos activos o superusuarios."""
    user = request.user
    if user.is_superuser:
        return
    perfil = getattr(user, "perfil_tecnico", None)
    if perfil is None or not perfil.activo:
        raise HttpError(403, "La clave de API no pertenece a un técnico activo")


def _usuario(user) -> str:
    """El nombre corto de Google Workspace, como lo enseña el panel."""
    email = user.email or ""
    return email.split("@", 1)[0] if email else str(user)


# ---------------------------------------------------------------------------
# Esquemas
# ---------------------------------------------------------------------------


class UbicacionOut(Schema):
    id: int
    nombre: str
    grupo: str
    planta: str
    planta_nombre: str


class EtiquetaOut(Schema):
    id: int
    nombre: str
    slug: str


class TecnicoOut(Schema):
    id: int
    nombre: str
    usuario: str
    activo: bool
    abiertas: int


class IncidenciaResumenOut(Schema):
    id: int
    titulo: str
    estado: str
    urgencia: str
    es_privada: bool
    reportero: str
    ubicacion: UbicacionOut | None
    etiquetas: list[EtiquetaOut]
    asignado_a: TecnicoOut | None
    n_comentarios: int
    n_adjuntos: int
    created_at: datetime
    updated_at: datetime
    url: str


class AdjuntoOut(Schema):
    id: int
    nombre: str
    url: str
    tipo: str
    comentario_id: int | None
    created_at: datetime


class ComentarioOut(Schema):
    id: int
    autor: str
    texto: str
    adjuntos: list[AdjuntoOut]
    created_at: datetime


class AsignacionOut(Schema):
    id: int
    asignado_por: str | None
    asignado_a: str | None
    nota: str
    created_at: datetime


class EmailOrigenOut(Schema):
    asunto: str
    remitente: str
    processed_at: datetime


class IncidenciaDetalleOut(IncidenciaResumenOut):
    descripcion: str
    comentarios: list[ComentarioOut]
    adjuntos: list[AdjuntoOut]
    historial_asignaciones: list[AsignacionOut]
    emails_origen: list[EmailOrigenOut]


class ListaOut(Schema):
    total: int
    page: int
    limit: int
    items: list[IncidenciaResumenOut]


class ConteoOut(Schema):
    clave: str
    nombre: str
    n: int


class ResumenOut(Schema):
    total: int
    abiertas: int
    por_estado: list[ConteoOut]
    por_urgencia: list[ConteoOut]
    por_tecnico: list[ConteoOut]
    por_etiqueta: list[ConteoOut]
    por_planta: list[ConteoOut]
    abiertas_sin_asignar: int
    abiertas_sin_ubicacion: int
    abierta_mas_antigua: date | None


# ---------------------------------------------------------------------------
# Serialización
# ---------------------------------------------------------------------------


def _ubicacion(u: Ubicacion | None) -> dict | None:
    if u is None:
        return None
    return {
        "id": u.id,
        "nombre": u.nombre,
        "grupo": u.grupo,
        "planta": u.planta,
        "planta_nombre": u.get_planta_display(),
    }


def _tecnico(t: Tecnico | None, abiertas: int | None = None) -> dict | None:
    if t is None:
        return None
    if abiertas is None:
        abiertas = t.incidencias_asignadas.exclude(
            estado=Incidencia.Estado.RESUELTA,
        ).count()
    return {
        "id": t.id,
        "nombre": str(t),
        "usuario": _usuario(t.user),
        "activo": t.activo,
        "abiertas": abiertas,
    }


def _adjunto(request, a) -> dict:
    tipo = (
        "imagen"
        if a.is_image
        else "video"
        if a.is_video
        else "pdf"
        if a.is_pdf
        else "otro"
    )
    return {
        "id": a.id,
        "nombre": a.archivo.name.rsplit("/", 1)[-1],
        "url": request.build_absolute_uri(a.archivo.url),
        "tipo": tipo,
        "comentario_id": a.comentario_id,
        "created_at": a.created_at,
    }


def _resumen(request, i: Incidencia) -> dict:
    return {
        "id": i.id,
        "titulo": i.titulo,
        "estado": i.estado,
        "urgencia": i.urgencia,
        "es_privada": i.es_privada,
        "reportero": i.reportero_nombre,
        "ubicacion": _ubicacion(i.ubicacion),
        "etiquetas": [
            {"id": e.id, "nombre": e.nombre, "slug": e.slug} for e in i.etiquetas.all()
        ],
        "asignado_a": _tecnico(i.asignado_a),
        "n_comentarios": i.n_comentarios
        if hasattr(i, "n_comentarios")
        else i.comentarios.count(),
        "n_adjuntos": i.n_adjuntos if hasattr(i, "n_adjuntos") else i.adjuntos.count(),
        "created_at": i.created_at,
        "updated_at": i.updated_at,
        "url": request.build_absolute_uri(f"/incidencias/{i.id}/"),
    }


def _detalle(request, i: Incidencia) -> dict:
    datos = _resumen(request, i)
    datos["descripcion"] = i.descripcion
    datos["comentarios"] = [
        {
            "id": c.id,
            "autor": c.autor_nombre,
            "texto": c.texto,
            "adjuntos": [_adjunto(request, a) for a in c.adjuntos.all()],
            "created_at": c.created_at,
        }
        for c in i.comentarios.prefetch_related("adjuntos")
    ]
    datos["adjuntos"] = [
        _adjunto(request, a) for a in i.adjuntos.filter(comentario__isnull=True)
    ]
    datos["historial_asignaciones"] = [
        {
            "id": h.id,
            "asignado_por": str(h.asignado_por) if h.asignado_por else None,
            "asignado_a": str(h.asignado_a) if h.asignado_a else None,
            "nota": h.nota,
            "created_at": h.created_at,
        }
        for h in i.historial_asignaciones.select_related(
            "asignado_por__user", "asignado_a__user",
        )
    ]
    datos["emails_origen"] = [
        {
            "asunto": e.raw_subject,
            "remitente": e.raw_sender,
            "processed_at": e.processed_at,
        }
        for e in i.emails_origen.all()
    ]
    return datos


def _base_queryset():
    return (
        Incidencia.objects.select_related("ubicacion", "asignado_a__user")
        .prefetch_related("etiquetas")
        .annotate(
            n_comentarios=Count("comentarios", distinct=True),
            n_adjuntos=Count("adjuntos", distinct=True),
        )
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response=ListaOut, url_name="incidencias_lista")
def listar_incidencias(  # noqa: PLR0913
    request,
    estado: str | None = None,
    urgencia: str | None = None,
    tecnico: str | None = None,
    etiqueta: str | None = None,
    ubicacion: int | None = None,
    planta: str | None = None,
    q: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    sin_ubicacion: bool = False,
    orden: str = "-created_at",
    page: int = 1,
    limit: int = 100,
):
    """Lista incidencias con filtros.

    - `estado`: uno o varios separados por coma (`pendiente,en_progreso`); `abiertas` = todo menos resuelta.
    - `tecnico`: id numérico, usuario (`jlopez`) o `sin_asignar`.
    - `etiqueta`: slug. `planta`: PB, P1 o P2. `q`: busca en título y descripción.
    - `desde` / `hasta`: fecha de creación (AAAA-MM-DD, inclusive).
    - `orden`: `created_at`, `-created_at`, `updated_at`, `-updated_at`, `urgencia`.
    """
    _exigir_tecnico(request)
    qs = _base_queryset()

    if estado:
        if estado == "abiertas":
            qs = qs.exclude(estado=Incidencia.Estado.RESUELTA)
        else:
            qs = qs.filter(
                estado__in=[e.strip() for e in estado.split(",") if e.strip()],
            )
    if urgencia:
        qs = qs.filter(
            urgencia__in=[u.strip() for u in urgencia.split(",") if u.strip()],
        )
    if tecnico:
        if tecnico == "sin_asignar":
            qs = qs.filter(asignado_a__isnull=True)
        elif tecnico.isdigit():
            qs = qs.filter(asignado_a_id=int(tecnico))
        else:
            qs = qs.filter(asignado_a__user__email__istartswith=f"{tecnico}@")
    if etiqueta:
        qs = qs.filter(etiquetas__slug=etiqueta)
    if ubicacion:
        qs = qs.filter(ubicacion_id=ubicacion)
    if planta:
        qs = qs.filter(ubicacion__planta=planta)
    if sin_ubicacion:
        qs = qs.filter(ubicacion__isnull=True)
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(descripcion__icontains=q))
    if desde:
        qs = qs.filter(created_at__date__gte=desde)
    if hasta:
        qs = qs.filter(created_at__date__lte=hasta)

    ordenes = {
        "created_at",
        "-created_at",
        "updated_at",
        "-updated_at",
        "urgencia",
        "-urgencia",
    }
    if orden not in ordenes:
        raise HttpError(422, f"orden debe ser uno de {sorted(ordenes)}")
    qs = qs.order_by(orden, "-id").distinct()

    limit = max(1, min(limit, LIMITE_MAXIMO))
    page = max(1, page)
    total = qs.count()
    inicio = (page - 1) * limit
    items = [_resumen(request, i) for i in qs[inicio : inicio + limit]]
    return {"total": total, "page": page, "limit": limit, "items": items}


@router.get("/resumen", response=ResumenOut, url_name="incidencias_resumen")
def resumen_incidencias(request):
    """Conteos globales: por estado, urgencia, técnico, etiqueta y planta, y huecos de datos."""
    _exigir_tecnico(request)
    todas = Incidencia.objects.all()
    abiertas = todas.exclude(estado=Incidencia.Estado.RESUELTA)

    def conteo(qs, campo, nombres):
        filas = qs.values(campo).annotate(n=Count("id", distinct=True)).order_by("-n")
        return [
            {"clave": str(f[campo]), "nombre": nombres(f[campo]), "n": f["n"]}
            for f in filas
        ]

    # Las etiquetas de `choices` son proxies perezosos de traducción: pydantic no los acepta como str.
    estados = {k: str(v) for k, v in Incidencia.Estado.choices}
    urgencias = {k: str(v) for k, v in Incidencia.Urgencia.choices}
    plantas = {k: str(v) for k, v in Ubicacion.Planta.choices}
    tecnicos = {t.id: str(t) for t in Tecnico.objects.select_related("user")}
    etiquetas = {e.id: e.nombre for e in Etiqueta.objects.all()}

    mas_antigua = (
        abiertas.order_by("created_at").values_list("created_at", flat=True).first()
    )

    return {
        "total": todas.count(),
        "abiertas": abiertas.count(),
        "por_estado": conteo(todas, "estado", lambda k: estados.get(k, k)),
        "por_urgencia": conteo(todas, "urgencia", lambda k: urgencias.get(k, k)),
        "por_tecnico": conteo(
            abiertas, "asignado_a", lambda k: tecnicos.get(k, "Sin asignar"),
        ),
        "por_etiqueta": conteo(
            abiertas, "etiquetas", lambda k: etiquetas.get(k, "Sin etiqueta"),
        ),
        "por_planta": conteo(
            abiertas, "ubicacion__planta", lambda k: plantas.get(k, "Sin ubicación"),
        ),
        "abiertas_sin_asignar": abiertas.filter(asignado_a__isnull=True).count(),
        "abiertas_sin_ubicacion": abiertas.filter(ubicacion__isnull=True).count(),
        "abierta_mas_antigua": mas_antigua.date() if mas_antigua else None,
    }


@router.get("/tecnicos", response=list[TecnicoOut], url_name="incidencias_tecnicos")
def listar_tecnicos(request, activos: bool | None = None):
    """Técnicos con su número de incidencias abiertas. `activos=true|false` filtra."""
    _exigir_tecnico(request)
    qs = Tecnico.objects.select_related("user").annotate(
        abiertas=Count(
            "incidencias_asignadas",
            filter=~Q(incidencias_asignadas__estado=Incidencia.Estado.RESUELTA),
        ),
    )
    if activos is not None:
        qs = qs.filter(activo=activos)
    return [_tecnico(t, t.abiertas) for t in qs.order_by("-activo", "id")]


@router.get("/etiquetas", response=list[EtiquetaOut], url_name="incidencias_etiquetas")
def listar_etiquetas(request):
    _exigir_tecnico(request)
    return list(Etiqueta.objects.values("id", "nombre", "slug"))


@router.get(
    "/ubicaciones", response=list[UbicacionOut], url_name="incidencias_ubicaciones",
)
def listar_ubicaciones(request):
    _exigir_tecnico(request)
    return [_ubicacion(u) for u in Ubicacion.objects.all()]


@router.get(
    "/{int:incidencia_id}",
    response=IncidenciaDetalleOut,
    url_name="incidencias_detalle",
)
def detalle_incidencia(request, incidencia_id: int):
    """Una incidencia con descripción, comentarios, adjuntos, historial de asignación y correos de origen."""
    _exigir_tecnico(request)
    i = get_object_or_404(_base_queryset(), pk=incidencia_id)
    return _detalle(request, i)
