"""API del plano de clase y de lo que pasa en las sesiones (fase 70).

Para que Illa recoloque al alumnado a partir de las notas que Jesús guarda en
su ordenador. Esas notas **no** pasan por aquí: el servidor solo sabe dónde se
sienta cada uno, la asistencia y lo que el propio profesor dejó en sus
sesiones (reflexión y notas de voz transcritas).

Clave en la cabecera `X-API-Key`. Solo se ven los grupos donde el dueño de la
clave es profesor (o todos, si es staff); el resto da 404, como en las
pantallas. Toda escritura pasa por `clases/plano.py`: misma validación que el
editor y una versión con motivo por cada cambio.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja import Schema
from ninja.errors import HttpError

from api_keys.auth import DatabaseApiKey
from clases import plano as planos
from clases.models import AULAS
from clases.models import ClassSession
from clases.models import Group
from clases.models import PlanoVersion
from clases.models import SessionNote
from martina_bescos_app.users.permisos import grupo_del_profesor

router = Router(tags=["Clases"], auth=DatabaseApiKey())


class PlanoIn(Schema):
    disposicion: dict
    motivo: str


def _grupo(request, group_id):
    return grupo_del_profesor(request.user, group_id)


def _aula(aula):
    if aula not in planos.CLAVES_AULA:
        raise HttpError(404, f"Aula desconocida: {aula}. Valen: {', '.join(sorted(planos.CLAVES_AULA))}")
    return aula


def _plano_json(plano):
    return {
        "grupo": plano.group.name,
        "aula": plano.aula,
        "disposicion": plano.disposicion,
        "alumnado": planos.alumnado_json(plano.group),
        "sin_sitio": [u.pk for u in planos.sin_sitio(plano)],
        "versiones": planos.versiones_json(plano),
    }


def _sesiones(request, group, desde, hasta):
    """Solo las sesiones del dueño de la clave: reflexiones y notas son de quien da la clase."""
    qs = ClassSession.objects.filter(group=group, teacher=request.user).order_by("date", "pk")
    if desde:
        qs = qs.filter(date__gte=desde)
    if hasta:
        qs = qs.filter(date__lte=hasta)
    return qs


@router.get("/grupos")
def grupos(request):
    """Mis grupos sin archivar. Solo los míos aunque la clave sea de staff."""
    qs = Group.objects.filter(archivado=False, teachers=request.user)
    resultado = []
    for g in qs.order_by("name").distinct():
        con_plano = set(g.planos.exclude(disposicion={}).values_list("aula", flat=True))
        resultado.append({
            "id": g.pk,
            "nombre": g.name,
            "curso": g.academic_year,
            "alumnado": len(planos.alumnado(g)),
            "aulas": [{"clave": c, "nombre": n, "tiene_plano": c in con_plano} for c, n in AULAS],
        })
    return resultado


@router.get("/grupos/{group_id}/planos/{aula}")
def leer_plano(request, group_id: int, aula: str):
    return _plano_json(planos.plano_de(_grupo(request, group_id), _aula(aula)))


@router.put("/grupos/{group_id}/planos/{aula}")
def escribir_plano(request, group_id: int, aula: str, cuerpo: PlanoIn):
    """Reescribe el plano entero. El motivo es obligatorio: es lo que el profesor lee en el historial."""
    if not cuerpo.motivo.strip():
        raise HttpError(422, "Falta el motivo: es lo que verá el profesor en el historial")
    plano = planos.plano_de(_grupo(request, group_id), _aula(aula))
    try:
        planos.guardar(plano, cuerpo.disposicion, autor=request.user,
                       origen=PlanoVersion.API, motivo=cuerpo.motivo)
    except ValidationError as e:
        raise HttpError(422, " · ".join(e.messages)) from e
    return _plano_json(plano)


@router.post("/grupos/{group_id}/planos/{aula}/restaurar/{version_id}")
def restaurar_plano(request, group_id: int, aula: str, version_id: int):
    plano = planos.plano_de(_grupo(request, group_id), _aula(aula))
    version = get_object_or_404(PlanoVersion, pk=version_id, plano=plano)
    planos.restaurar(version, autor=request.user)
    plano.refresh_from_db()
    return _plano_json(plano)


@router.get("/grupos/{group_id}/asistencia")
def asistencia(request, group_id: int, desde: date | None = None, hasta: date | None = None):
    """Por sesión: aula, si se pasó lista y las marcas (solo las que hay: sin marca es presente)."""
    group = _grupo(request, group_id)
    resultado = []
    for s in _sesiones(request, group, desde, hasta).select_related("pase_de_lista").prefetch_related("asistencias__alumno"):
        pase = getattr(s, "pase_de_lista", None)
        resultado.append({
            "sesion": s.pk,
            "fecha": s.date.isoformat(),
            "titulo": s.title,
            "aula": pase.aula if pase else None,
            "lista_pasada": bool(pase and pase.pasada_at),
            "marcas": [
                {"alumno": a.alumno_id, "nombre": a.alumno.name or a.alumno.email, **planos.asistencia_json(a)}
                for a in s.asistencias.all()
            ],
        })
    return resultado


@router.get("/grupos/{group_id}/sesiones")
def sesiones(request, group_id: int, desde: date | None = None, hasta: date | None = None):
    """Lo que el profesor dejó dicho de cada clase: reflexión y notas de voz ya transcritas."""
    group = _grupo(request, group_id)
    resultado = []
    for s in _sesiones(request, group, desde, hasta).prefetch_related("notas"):
        resultado.append({
            "sesion": s.pk,
            "fecha": s.date.isoformat(),
            "titulo": s.title,
            "cerrada": s.closed_at is not None,
            "reflexion": s.reflection,
            "notas": [
                {"elemento": n.item_titulo, "transcripcion": n.transcripcion, "estado": n.estado}
                for n in s.notas.all()
                if n.transcripcion or n.estado != SessionNote.PENDIENTE
            ],
        })
    return resultado

