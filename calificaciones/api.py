"""API de lectura de las calificaciones (fase 81).

Para que Illa conteste a un tutor sin abrir la pantalla: «¿es alumno mío?»,
«¿qué notas tiene?», «¿quién le puso qué y cuándo?». Todo lo que sale de aquí
es exactamente lo que ya pinta la pantalla de calificaciones: `estado.estado()`
y `estado.historial()` son los mismos que usan las vistas, con las cifras ya
escritas como texto. No hay un segundo cálculo.

Solo lectura. Las notas se escriben desde la pantalla, donde cada cambio queda
en el historial con quién y cuándo; una API que escribiera notas a ciegas
tendría que repetir eso y no hace falta hoy.

Clave en la cabecera `X-API-Key`. Solo se ven los grupos donde el dueño de la
clave es profesor (o todos, si es staff); el resto da 404, como en las
pantallas. Un alumno solo existe para la clave si está matriculado y activo en
uno de esos grupos.
"""

from __future__ import annotations

from django.db.models import Q
from ninja import Router
from ninja.errors import HttpError

from api_keys.auth import DatabaseApiKey
from clases.models import Group
from martina_bescos_app.users.permisos import grupo_del_profesor

from . import estado
from .models import CambioNota
from .models import Evidencia
from .models import RevisionCuaderno
from .models import alumnos_del_grupo

router = Router(tags=["Calificaciones"], auth=DatabaseApiKey())

TRIMESTRES = ("1", "2", "3")
HISTORIAL_MAXIMO = 2000
BUSQUEDA_MINIMA = 2


def _grupo(request, group_id):
    return grupo_del_profesor(request.user, group_id)


def _mis_grupos(user):
    """Lo mismo que el índice de calificaciones: los grupos activos del profesor."""
    return (
        Group.del_profesor(user)
        .select_related("subject")
        .prefetch_related("planes_calificacion")
    )


def _grupo_json(group) -> dict:
    planes = {str(p.trimestre): p for p in group.planes_calificacion.all()}
    return {
        "id": group.pk,
        "nombre": group.name,
        "materia": group.subject.name,
        "curso": group.academic_year,
        "alumnado": alumnos_del_grupo(group).count(),
        "planes": {
            t: (
                {"id": planes[t].pk, "nombre": planes[t].nombre}
                if t in planes
                else None
            )
            for t in TRIMESTRES
        },
    }


def _alumno_json(alumno, grupos) -> dict:
    return {
        "id": alumno.pk,
        "nombre": alumno.name or alumno.email,
        "email": alumno.email,
        "grupos": [{"id": g.pk, "nombre": g.name} for g in grupos],
    }


def _revision_json(r: RevisionCuaderno) -> dict:
    return {
        "id": r.pk,
        "alumno": r.alumno_id,
        "sesion": r.session_id,
        "fecha": r.session.date.isoformat(),
        "instrumento": r.instrumento.nombre,
        "letra": r.letra,
        "valor": CambioNota.texto(r.valor),
        "comentario": r.comentario,
        "autor": (r.autor.name or r.autor.email) if r.autor else "",
    }


def _revisiones(group, alumno=None):
    qs = RevisionCuaderno.objects.filter(instrumento__plan__groups=group).exclude(
        letra="",
    )
    if alumno is not None:
        qs = qs.filter(alumno=alumno)
    return [
        _revision_json(r)
        for r in qs.select_related("session", "instrumento", "autor").distinct()
    ]


def _grupos_del_alumno(user, alumno_id):
    """Los grupos míos donde este alumno está matriculado y activo. Vacío = 404."""
    return [
        g
        for g in _mis_grupos(user)
        if g.enrollments.filter(user_id=alumno_id, is_active=True).exists()
    ]


# ----- grupos -----------------------------------------------------------------------


@router.get("/grupos")
def grupos(request):
    """Mis grupos sin archivar y qué trimestres tienen plan. Como el índice de la pantalla."""
    return [_grupo_json(g) for g in _mis_grupos(request.user).order_by("name")]


@router.get("/grupos/{group_id}")
def grupo(request, group_id: int):
    """Todo lo que pinta la pantalla del grupo: plan, columnas, celdas, cifras, evidencias.

    Es `estado.estado()` tal cual: `alumnos[].trimestres[t].notas` por prueba,
    `nota`/`cualitativa`/`competencias` por trimestre y `curso` al final.
    """
    return estado.estado(_grupo(request, group_id), request.user)


@router.get("/grupos/{group_id}/historial")
def historial(request, group_id: int, limite: int = 300):
    """Cada cambio de nota del grupo: alumno, columna, antes, después, quién y cuándo."""
    if not 1 <= limite <= HISTORIAL_MAXIMO:
        raise HttpError(422, f"limite tiene que estar entre 1 y {HISTORIAL_MAXIMO}")
    return {"cambios": estado.historial(_grupo(request, group_id), limite)}


@router.get("/grupos/{group_id}/cuaderno")
def cuaderno(request, group_id: int):
    """Las revisiones del cuaderno (el dado del pase de lista) con letra, por fecha."""
    return {"revisiones": _revisiones(_grupo(request, group_id))}


# ----- alumnos ----------------------------------------------------------------------


@router.get("/alumnos")
def alumnos(request, q: str):
    """¿Es alumno mío? Busca por nombre o correo en el alumnado activo de mis grupos.

    Devuelve cada alumno una vez, con los grupos míos en los que está. Dos
    letras como mínimo: con menos, la lista es el centro entero.
    """
    q = q.strip()
    if len(q) < BUSQUEDA_MINIMA:
        raise HttpError(422, "q necesita al menos dos caracteres")
    encontrados: dict[int, tuple] = {}
    for g in _mis_grupos(request.user).order_by("name"):
        for a in alumnos_del_grupo(g).filter(
            Q(name__icontains=q) | Q(email__icontains=q),
        ):
            alumno, grupos_de = encontrados.setdefault(a.pk, (a, []))
            grupos_de.append(g)
    return [
        _alumno_json(a, gs)
        for a, gs in sorted(
            encontrados.values(),
            key=lambda x: (x[0].name or "", x[0].pk),
        )
    ]


@router.get("/alumnos/{alumno_id}")
def alumno(request, alumno_id: int):
    """La ficha de un alumno en todos mis grupos: celdas, cifras, evidencias, cuaderno, cambios."""
    grupos_de = _grupos_del_alumno(request.user, alumno_id)
    if not grupos_de:
        raise HttpError(404, "No existe ese alumno en tus grupos")
    persona = grupos_de[0].enrollments.get(user_id=alumno_id, is_active=True).user
    fichas = []
    for g in grupos_de:
        fichas.append(
            {
                "grupo": {
                    "id": g.pk,
                    "nombre": g.name,
                    "materia": g.subject.name,
                    "curso": g.academic_year,
                },
                "calificaciones": estado.bloque_alumno(g, persona),
                "evidencias": [
                    estado.evidencia_json(e)
                    for e in Evidencia.objects.filter(
                        prueba__instrumento__plan__groups=g,
                        alumno=persona,
                    ).distinct()
                ],
                "cuaderno": _revisiones(g, persona),
                "cambios": [
                    c
                    for c in estado.historial(g, HISTORIAL_MAXIMO)
                    if c["alumno_id"] == persona.pk
                ],
            },
        )
    return {**_alumno_json(persona, grupos_de), "fichas": fichas}
