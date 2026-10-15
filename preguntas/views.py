"""Prototipo de escaneo (fase 76·0). Sin modelos: nada se guarda.

Los fotogramas se leen en memoria y se descartan: ni disco, ni `Evidencia`,
ni cuerpo en los logs (son menores). Solo se registra cuántos marcadores y
cuánto tardó, que es lo que la claim C472 necesita medir.
"""

import logging
import time

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from martina_bescos_app.users.permisos import es_profesor

from . import aruco
from . import tarjetas as tarjetas_pdf

logger = logging.getLogger(__name__)

TAMANO_MAXIMO = 2_000_000  # un JPEG de 640×480 pesa 30–80 KB; esto es holgura
TARJETAS_DE_PRUEBA = 10


@login_required
@user_passes_test(es_profesor)
@require_GET
def prototipo(request):
    return render(request, "preguntas/prototipo.html", {"n_tarjetas": TARJETAS_DE_PRUEBA})


@login_required
@user_passes_test(es_profesor)
@require_POST
def detectar(request):
    """Un fotograma (campo `frame` multipart, o el cuerpo entero) → marcadores leídos."""
    # Con multipart, tocar FILES consume el flujo y `request.body` ya no se puede
    # leer; por eso se decide por el tipo de contenido y no se mezclan los dos.
    if request.content_type == "multipart/form-data":
        fichero = request.FILES.get("frame")
        datos = fichero.read() if fichero is not None else b""
    else:
        datos = request.body
    if not datos:
        return JsonResponse({"error": "Falta la imagen"}, status=400)
    if len(datos) > TAMANO_MAXIMO:
        return JsonResponse({"error": "Imagen demasiado grande"}, status=400)
    empieza = time.perf_counter()
    try:
        marcadores = aruco.detectar(datos)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    ms = (time.perf_counter() - empieza) * 1000
    logger.info("preguntas.detectar: %d marcadores en %.1f ms", len(marcadores), ms)
    return JsonResponse({"marcadores": marcadores, "ms": round(ms, 1)})


@login_required
@user_passes_test(es_profesor)
@require_GET
def tarjetas_prueba(request):
    """Diez tarjetas numeradas para calibrar distancia y luz en el aula (C471)."""
    tarjetas = [
        {"id": n, "numero": n, "nombre": f"Tarjeta de prueba {n}"}
        for n in range(1, TARJETAS_DE_PRUEBA + 1)
    ]
    respuesta = HttpResponse(tarjetas_pdf.pdf_tarjetas(tarjetas), content_type="application/pdf")
    respuesta["Content-Disposition"] = 'inline; filename="tarjetas-prueba.pdf"'
    return respuesta
