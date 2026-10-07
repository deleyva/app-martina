"""Pantallas del plano de clase (fase 70): el editor y el pase de lista en clase.

Las dos hablan JSON con el mismo `clases/static/clases/plano.js`. Toda regla
vive en `clases/plano.py`; aquí solo se comprueba quién es y se traduce.
"""

import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from clases import plano as planos
from clases.models import AULAS
from clases.models import ClassSession
from clases.models import PlanoVersion
from martina_bescos_app.users.permisos import es_profesor
from martina_bescos_app.users.permisos import grupo_del_profesor


def _cuerpo(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError as e:
        raise ValidationError("El cuerpo no es JSON") from e


def _error(e):
    return JsonResponse({"errores": e.messages}, status=422)


def _aula(aula):
    if aula not in planos.CLAVES_AULA:
        raise Http404("Aula desconocida")
    return aula


def _datos_editor(plano):
    return {
        "aula": plano.aula,
        "disposicion": plano.disposicion,
        "alumnado": planos.alumnado_json(plano.group),
        "sin_sitio": [u.pk for u in planos.sin_sitio(plano)],
        "versiones": planos.versiones_json(plano),
    }


# -----------------------------------------------------------------------------
# Editor
# -----------------------------------------------------------------------------


@login_required
@user_passes_test(es_profesor)
def plano_editor(request, group_id, aula):
    grupo = grupo_del_profesor(request.user, group_id)
    plano = planos.plano_de(grupo, _aula(aula))
    return render(
        request,
        "clases/plano/editor.html",
        {
            "group": grupo,
            "aula": aula,
            "aulas": AULAS,
            "datos": _datos_editor(plano),
            "rejilla": planos.rejilla(),
        },
    )


@login_required
@user_passes_test(es_profesor)
@require_GET
def plano_datos(request, group_id, aula):
    grupo = grupo_del_profesor(request.user, group_id)
    return JsonResponse(_datos_editor(planos.plano_de(grupo, _aula(aula))))


@login_required
@user_passes_test(es_profesor)
@require_POST
def plano_guardar(request, group_id, aula):
    grupo = grupo_del_profesor(request.user, group_id)
    plano = planos.plano_de(grupo, _aula(aula))
    try:
        cuerpo = _cuerpo(request)
        planos.guardar(
            plano, cuerpo.get("disposicion"), autor=request.user,
            origen=PlanoVersion.PANTALLA, motivo=cuerpo.get("motivo", ""),
        )
    except ValidationError as e:
        return _error(e)
    return JsonResponse(_datos_editor(plano))


@login_required
@user_passes_test(es_profesor)
@require_POST
def plano_restaurar(request, group_id, aula, version_id):
    grupo = grupo_del_profesor(request.user, group_id)
    plano = planos.plano_de(grupo, _aula(aula))
    version = get_object_or_404(PlanoVersion, pk=version_id, plano=plano)
    planos.restaurar(version, autor=request.user)
    plano.refresh_from_db()
    return JsonResponse(_datos_editor(plano))


# -----------------------------------------------------------------------------
# Pasar lista, desde la clase
# -----------------------------------------------------------------------------


def _sesion_del_profesor(request, pk):
    """Solo quien da la sesión, como en el resto de pantallas de sesión.

    Un cotitular del grupo no pasa lista en la clase de otro: es la misma regla
    que decide si `present` enseña el plano.
    """
    session = get_object_or_404(ClassSession.objects.select_related("group"), pk=pk, teacher=request.user)
    grupo_del_profesor(request.user, session.group_id)
    return session


@login_required
@user_passes_test(es_profesor)
@require_GET
def lista_datos(request, pk):
    session = _sesion_del_profesor(request, pk)
    return JsonResponse(planos.datos_de_lista(session, aula=request.GET.get("aula")))


@login_required
@user_passes_test(es_profesor)
@require_POST
def lista_marcar(request, pk):
    """Cuerpo JSON: {alumno, estado?, sin_material?, nota?}. Lo que no llega no cambia."""
    session = _sesion_del_profesor(request, pk)
    try:
        cuerpo = _cuerpo(request)
        alumno = cuerpo.get("alumno")
        if not isinstance(alumno, int):
            raise ValidationError("Falta el alumno")
        fila = planos.marcar(
            session, alumno, estado=cuerpo.get("estado"),
            sin_material=cuerpo.get("sin_material"), nota=cuerpo.get("nota"),
        )
    except ValidationError as e:
        return _error(e)
    return JsonResponse({
        "alumno": alumno,
        "asistencia": planos.asistencia_json(fila) if fila else None,
        "resumen": planos.resumen_sigad(session),
    })


@login_required
@user_passes_test(es_profesor)
@require_POST
def lista_pasada(request, pk):
    session = _sesion_del_profesor(request, pk)
    planos.dar_por_pasada(session)
    return JsonResponse({"pasada": True, "resumen": planos.resumen_sigad(session)})
