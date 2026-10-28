"""Pistas de práctica del visor ChordPro (fase 82): subir, oír, cambiar y borrar.

**Oír** pide sesión y nada más: el alumnado practica en casa con su cuenta del
centro. **Subir, cambiar y borrar** pide lo mismo que el ✎ de la letra, poder
editar la canción en Wagtail (`letras.puede_editar`).

El fichero nunca sale por `/media/`: nginx cierra `/media/pistas_practica/` y
la única puerta es `pista_audio`. Se entrega entero y sin rangos a propósito:
el reproductor lo descarga una vez y lo decodifica, porque cambiar velocidad y
hacer bucles sin tocar el tono exige tener el búfer completo.
"""

import json

from django.contrib.auth.decorators import login_required
from django.http import (
    FileResponse,
    Http404,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from musica.letras import puede_editar
from musica.models import PistaDePractica, RecursoPage


@require_GET
@login_required
def pista_audio(request, pk):
    pista = get_object_or_404(PistaDePractica, pk=pk)
    if not pista.archivo:
        raise Http404("Esta pista no tiene audio.")
    respuesta = FileResponse(pista.archivo.open("rb"))
    # El fichero de una pista no cambia nunca (no se resube: se borra y se crea
    # otra), así que el navegador puede guardarlo. `private`: nada de cachés
    # compartidas por el camino.
    respuesta["Cache-Control"] = "private, max-age=604800"
    return respuesta


@require_POST
def pista_subir(request, page_id):
    recurso = get_object_or_404(RecursoPage, pk=page_id).specific
    if not puede_editar(recurso, request.user):
        return HttpResponseForbidden("No puedes añadir audio a esta canción.")
    try:
        pista = PistaDePractica.crear(
            recurso,
            request.FILES.get("archivo"),
            request.POST.get("nombre"),
            request.POST.get("semitonos", 0),
            usuario=request.user,
        )
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse(pista.a_json(), status=201)


@require_POST
def pista_guardar(request, pk):
    pista = get_object_or_404(PistaDePractica, pk=pk)
    if not puede_editar(pista.recurso.specific, request.user):
        return HttpResponseForbidden("No puedes cambiar esta pista.")
    try:
        datos = json.loads(request.body or b"{}")
    except ValueError:
        return HttpResponseBadRequest("JSON no válido.")
    if not isinstance(datos, dict):
        return HttpResponseBadRequest("JSON no válido.")
    try:
        pista.actualizar(datos)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse(pista.a_json())


@require_POST
def pista_borrar(request, pk):
    pista = get_object_or_404(PistaDePractica, pk=pk)
    if not puede_editar(pista.recurso.specific, request.user):
        return HttpResponseForbidden("No puedes borrar esta pista.")
    pista.delete()
    return JsonResponse({"ok": True})
