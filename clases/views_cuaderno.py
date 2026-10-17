"""El dado del cuaderno en el pase de lista (fase 78): las vistas.

Finas: lo que decide algo vive en `calificaciones.cuaderno`. El permiso es el
del pase de lista (`_sesion_del_profesor`): solo quien da la sesión tira y
califica, igual que solo él pasa lista en ella.
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from calificaciones import cuaderno
from calificaciones.evaluar import instrumento_del_grupo
from clases.views_plano import _sesion_del_profesor
from martina_bescos_app.users.permisos import es_profesor


def _cuerpo(request):
    try:
        datos = json.loads(request.body or b"{}")
    except ValueError as e:
        raise ValidationError("El cuerpo no es JSON") from e
    if not isinstance(datos, dict):
        raise ValidationError("El cuerpo no es un objeto")
    return datos


def _error(mensaje, status=400):
    return JsonResponse({"error": mensaje}, status=status)


def _alumno(datos):
    alumno_id = str(datos.get("alumno") or "")
    alumno = get_user_model().objects.filter(pk=alumno_id).first() if alumno_id.isdigit() else None
    if alumno is None:
        raise ValidationError("Falta el alumno")
    return alumno


def _excluir(datos):
    excluir = datos.get("excluir") or []
    if not isinstance(excluir, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in excluir):
        raise ValidationError("`excluir` tiene que ser una lista de ids")
    return excluir


@login_required
@user_passes_test(es_profesor)
@require_GET
def cuaderno_estado(request, pk):
    session = _sesion_del_profesor(request, pk)
    return JsonResponse(cuaderno.estado_de_lista(session))


@login_required
@user_passes_test(es_profesor)
@require_POST
def cuaderno_sortear(request, pk):
    """Cuerpo JSON: {instrumento?, n?, excluir?}. `instrumento` solo hace falta si el trimestre no tiene «Cuaderno»."""
    session = _sesion_del_profesor(request, pk)
    try:
        datos = _cuerpo(request)
        instrumento = cuaderno.instrumento_de(session)
        if instrumento is None:
            instrumento = instrumento_del_grupo(session.group, datos.get("instrumento"))
        if instrumento is None:
            return _error("Elige con qué instrumento revisar el cuaderno")
        n = datos.get("n", cuaderno.POR_SESION)
        if isinstance(n, bool) or not isinstance(n, int):
            raise ValidationError("`n` tiene que ser un número")
        cuaderno.sortear(session, instrumento, n=n, excluir=_excluir(datos), autor=request.user)
    except (ValidationError, ValueError) as e:
        return _error(getattr(e, "message", None) or str(e))
    return JsonResponse(cuaderno.estado_de_lista(session))


@login_required
@user_passes_test(es_profesor)
@require_POST
def cuaderno_descartar(request, pk):
    """Cerrar la franja: fuera los pendientes de hoy; lo calificado se queda."""
    session = _sesion_del_profesor(request, pk)
    cuaderno.descartar(session)
    return JsonResponse(cuaderno.estado_de_lista(session))


@login_required
@user_passes_test(es_profesor)
@require_POST
def cuaderno_saltar(request, pk):
    """Cuerpo JSON: {alumno}. Le quita la pendiente y tira otra vez por uno, sin repetirle."""
    session = _sesion_del_profesor(request, pk)
    try:
        datos = _cuerpo(request)
        alumno = _alumno(datos)
        cuaderno.saltar(session, alumno.pk)
        instrumento = cuaderno.instrumento_de(session)
        if instrumento is not None:
            cuaderno.sortear(session, instrumento, n=1, excluir=[alumno.pk, *_excluir(datos)], autor=request.user)
    except (ValidationError, ValueError) as e:
        return _error(getattr(e, "message", None) or str(e))
    return JsonResponse(cuaderno.estado_de_lista(session))


@login_required
@user_passes_test(es_profesor)
@require_POST
def cuaderno_calificar(request, pk):
    """Cuerpo JSON: {alumno, letra, comentario?}."""
    session = _sesion_del_profesor(request, pk)
    try:
        datos = _cuerpo(request)
        alumno = _alumno(datos)
        fila, nota = cuaderno.calificar(
            session, alumno, str(datos.get("letra") or ""), request.user,
            comentario=str(datos.get("comentario") or ""),
        )
    except (ValidationError, ValueError) as e:
        return _error(getattr(e, "message", None) or str(e))
    estado = cuaderno.estado_de_lista(session)
    estado["guardado"] = {"alumno": fila.alumno_id, "letra": fila.letra, "casilla": nota.rubrica["acumulado"]["letra"]}
    return JsonResponse(estado)
