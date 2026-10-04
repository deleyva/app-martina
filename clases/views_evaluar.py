"""Evaluar en clase (fase 62): las vistas.

Finas: lo que decide algo vive en `calificaciones.evaluar`. El permiso es
siempre el del GRUPO de la sesión, igual que en calificaciones: cualquier
profesor del grupo puede evaluar a su alumnado, no solo quien creó la sesión.
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from calificaciones import evaluar
from clases.models import ClassSessionItem
from martina_bescos_app.users.permisos import es_profesor, grupo_del_profesor


def _elemento(request, pk):
    """El elemento de sesión y su grupo, si das clase a ese grupo. Si no, 404."""
    item = get_object_or_404(
        ClassSessionItem.objects.select_related("session__group", "instrumento__plan", "content_type"),
        pk=pk,
    )
    group = grupo_del_profesor(request.user, item.session.group_id)
    return item, group


def _instrumento_de(item, group):
    """El instrumento con el que se evalúa, comprobando que sigue siendo del grupo.

    El plan se le puede quitar al grupo después de marcar el elemento: entonces
    el elemento ya no es evaluable aquí, aunque la marca siga guardada.
    """
    if item.instrumento_id is None:
        raise Http404("Este elemento no es evaluable.")
    instrumento = evaluar.instrumento_del_grupo(group, item.instrumento_id)
    if instrumento is None:
        raise Http404("El instrumento ya no es de un plan de este grupo.")
    return instrumento


def _error(mensaje, status=400):
    return JsonResponse({"error": mensaje}, status=status)


# =============================================================================
# MARCAR EVALUABLE (al preparar la sesión)
# =============================================================================


@login_required
@user_passes_test(es_profesor)
@require_POST
def item_evaluable(request, pk):
    """Marca el elemento con un instrumento, o lo desmarca con `instrumento=""`.

    Devuelve el bloque del botón con su popup, que es lo que sustituye htmx.
    """
    item, group = _elemento(request, pk)
    valor = request.POST.get("instrumento", "")
    if valor == "":
        item.instrumento = None
    else:
        instrumento = evaluar.instrumento_del_grupo(group, valor)
        if instrumento is None:
            raise Http404("Ese instrumento no es de un plan de este grupo.")
        item.instrumento = instrumento
    item.save(update_fields=["instrumento"])
    return render(
        request,
        "clases/class_sessions/partials/evaluable.html",
        {"item": item, "planes": evaluar.instrumentos_del_grupo(group, item.session.date)},
    )


# =============================================================================
# EVALUAR (durante la clase, desde la presentación)
# =============================================================================


def _alumno_json(fila, instrumento):
    """Un alumno para el panel. `letra` vacía = sin nota en esa columna.

    La letra se lee del valor guardado y no de la rúbrica: si alguien la cambió
    después en el registro, manda lo que hay en el registro.
    """
    alumno, nota = fila["alumno"], fila["nota"]
    letra = instrumento.etiqueta_de(nota.valor) if nota else ""
    rubrica = (nota.rubrica or {}) if nota else {}
    # Los puntos guardados solo valen si la nota sigue siendo la que dieron. Si
    # luego se cambió en el registro, precargarlos proponía la letra vieja y un
    # toque en «Guardar» deshacía el cambio (revisión independiente, 2026-10-04).
    puntos = rubrica.get("puntos", []) if rubrica.get("letra") == letra else []
    return {
        "id": alumno.pk,
        "nombre": alumno.name or alumno.email,
        "letra": letra,
        "comentario": nota.comentario if nota else "",
        "puntos": puntos,
    }


@login_required
@user_passes_test(es_profesor)
@require_GET
def evaluar_estado(request, pk):
    """Lo que pinta el panel: instrumento, rúbrica, alumnado con su nota y la columna."""
    item, group = _elemento(request, pk)
    instrumento = _instrumento_de(item, group)
    situacion = evaluar.situacion(group, instrumento)
    prueba = situacion["prueba"]
    if prueba is None:
        return _error("Este instrumento no tiene ninguna columna activa en el registro")
    return JsonResponse(
        {
            "grupo": group.pk,
            "grupo_nombre": group.name,
            "prueba": prueba.pk,
            "prueba_nombre": prueba.nombre,
            "instrumento": {
                "id": instrumento.pk,
                "nombre": instrumento.nombre,
                "rubrica": list(instrumento.rubrica or []),
                "trimestre": instrumento.plan.trimestre,
            },
            "letras": evaluar.LETRAS,
            "alumnos": [_alumno_json(f, instrumento) for f in situacion["alumnos"]],
            "elemento": item.get_content_title(),
        }
    )


@login_required
@user_passes_test(es_profesor)
@require_GET
def evaluar_azar(request, pk):
    """Un alumno al azar entre quienes no tienen nota. `?excluir=3,8` salta ausentes."""
    item, group = _elemento(request, pk)
    instrumento = _instrumento_de(item, group)
    excluir = [x for x in request.GET.get("excluir", "").split(",") if x.strip().isdigit()]
    alumno = evaluar.al_azar(group, instrumento, excluir=excluir)
    quedan = len([a for a in evaluar.sin_nota(group, instrumento) if str(a.pk) not in excluir])
    if alumno is None:
        return JsonResponse({"alumno": None, "quedan": 0})
    return JsonResponse(
        {"alumno": {"id": alumno.pk, "nombre": alumno.name or alumno.email}, "quedan": quedan}
    )


@login_required
@user_passes_test(es_profesor)
@require_POST
def evaluar_guardar(request, pk):
    """Guarda la nota. Cuerpo JSON: {alumno, puntos?, letra?, comentario?}."""
    item, group = _elemento(request, pk)
    instrumento = _instrumento_de(item, group)
    try:
        datos = json.loads(request.body or "{}")
    except ValueError:
        return _error("Petición mal formada")
    if not isinstance(datos, dict):
        return _error("Petición mal formada")
    alumno_id = str(datos.get("alumno") or "")
    alumno = get_user_model().objects.filter(pk=alumno_id).first() if alumno_id.isdigit() else None
    if alumno is None:
        return _error("Falta el alumno")
    puntos = datos.get("puntos") or None
    if puntos is not None and not isinstance(puntos, list):
        return _error("Los puntos de la rúbrica van en una lista")
    try:
        nota = evaluar.evaluar(
            group=group,
            instrumento=instrumento,
            alumno=alumno,
            user=request.user,
            puntos=puntos,
            letra=str(datos.get("letra") or "") or None,
            comentario=str(datos.get("comentario") or ""),
            elemento=item,
        )
    except (ValueError, TypeError) as error:
        return _error(str(error))
    return JsonResponse(
        {
            "ok": True,
            "alumno": alumno.pk,
            "letra": nota.rubrica.get("letra"),
            "valor": str(nota.valor),
            "prueba": nota.prueba_id,
        }
    )
