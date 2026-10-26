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
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from martina_bescos_app.users.permisos import es_profesor

from . import aruco
from . import tarjetas as tarjetas_pdf

logger = logging.getLogger(__name__)

TAMANO_MAXIMO = 2_000_000  # un JPEG de 1920×1080 al 70 % pesa 150–500 KB; esto es holgura
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
    logger.info(
        "preguntas.detectar: %d marcadores %s en %.1f ms (%d bytes)",
        len(marcadores),
        [m["id"] for m in marcadores],
        ms,
        len(datos),
    )
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


# =============================================================================
# BANCO DE PREGUNTAS (tramo 76·1)
# =============================================================================

from django.contrib import messages  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402
from django.db.models import Count, Q  # noqa: E402
from django.shortcuts import get_object_or_404, redirect  # noqa: E402

from cms.etiquetas import facetas_desconocidas  # noqa: E402
from my_library import facets  # noqa: E402

from .models import OPCIONES, Pregunta  # noqa: E402


def _con_estadisticas(consulta):
    return consulta.annotate(
        veces=Count("pases", distinct=True),
        n_respuestas=Count("respuestas", distinct=True),
        n_aciertos=Count("respuestas", filter=Q(respuestas__acierto=True), distinct=True),
    ).prefetch_related("etiquetas")


def _porcentaje(pregunta):
    if not pregunta.n_respuestas:
        return None
    return round(100 * pregunta.n_aciertos / pregunta.n_respuestas)


@login_required
@user_passes_test(es_profesor)
@require_GET
def banco(request):
    """Lista por concepto, con filtro de estado y texto (C475)."""
    estado = request.GET.get("estado", "")
    texto = request.GET.get("q", "").strip()
    consulta = Pregunta.objects.all()
    if estado in dict(Pregunta.ESTADOS):
        consulta = consulta.filter(estado=estado)
    if texto:
        consulta = consulta.filter(Q(enunciado__icontains=texto) | Q(etiquetas__name__icontains=texto)).distinct()

    por_concepto = {}
    for pregunta in _con_estadisticas(consulta):
        pregunta.acierto = _porcentaje(pregunta)
        conceptos = pregunta.conceptos() or ["(sin concepto)"]
        por_concepto.setdefault(conceptos[0], []).append(pregunta)

    totales = {clave: Pregunta.objects.filter(estado=clave).count() for clave, _ in Pregunta.ESTADOS}
    return render(
        request,
        "preguntas/banco.html",
        {
            "grupos": sorted(por_concepto.items()),
            "estado": estado,
            "q": texto,
            "totales": totales,
            "estados": Pregunta.ESTADOS,
        },
    )


def _leer_formulario(request, pregunta):
    pregunta.enunciado = request.POST.get("enunciado", "").strip()
    pregunta.opciones = [request.POST.get(f"opcion_{i}", "").strip() for i in range(OPCIONES)]
    try:
        pregunta.correcta = int(request.POST.get("correcta", ""))
    except ValueError:
        pregunta.correcta = None
    pregunta.explicacion = request.POST.get("explicacion", "").strip()
    etiquetas = [e.strip() for e in request.POST.get("etiquetas", "").split(",") if e.strip()]
    malas = facetas_desconocidas(etiquetas)
    if malas:
        raise ValidationError({"etiquetas": f"Faceta desconocida: {', '.join(malas)}"})
    if not any(facets.valor_de(e, facets.CONCEPTO) for e in etiquetas):
        raise ValidationError({"etiquetas": "Hace falta al menos una etiqueta concepto:…"})
    return etiquetas


@login_required
@user_passes_test(es_profesor)
def editar(request, pk=None):
    pregunta = get_object_or_404(Pregunta, pk=pk) if pk else Pregunta(autor=request.user)
    errores = {}
    if request.method == "POST":
        try:
            etiquetas = _leer_formulario(request, pregunta)
            pregunta.full_clean(exclude=["etiquetas", "autor", "imagen"])
            pregunta.save()
            pregunta.etiquetas.set(etiquetas)
            messages.success(request, "Pregunta guardada.")
            return redirect(f"{reverse('preguntas:banco')}?estado={pregunta.estado}")
        except ValidationError as error:
            errores = {campo: " ".join(msgs) for campo, msgs in error.message_dict.items()}
    # Tras un POST con error se reenseña lo tecleado, no lo guardado.
    if request.method == "POST":
        opciones = [request.POST.get(f"opcion_{i}", "") for i in range(OPCIONES)]
    else:
        opciones = list(pregunta.opciones or []) + [""] * OPCIONES
    return render(
        request,
        "preguntas/editar.html",
        {
            "pregunta": pregunta,
            "opciones": list(enumerate(opciones[:OPCIONES])),
            "letras": Pregunta.LETRAS,
            "etiquetas": ", ".join(pregunta.etiquetas.names()) if pregunta.pk else "",
            "errores": errores,
            "valores": request.POST if request.method == "POST" else None,
        },
    )


@login_required
@user_passes_test(es_profesor)
@require_POST
def cambiar_estado(request, pk):
    pregunta = get_object_or_404(Pregunta, pk=pk)
    nuevo = request.POST.get("estado")
    if nuevo not in dict(Pregunta.ESTADOS):
        return HttpResponse("Estado desconocido", status=400)
    pregunta.estado = nuevo
    pregunta.save()
    return redirect(request.POST.get("volver") or reverse("preguntas:banco"))
