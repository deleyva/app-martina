"""El pase de preguntas en clase (tramo 76·2): las vistas.

Finas: lo que decide algo vive en `vivo.py`. El permiso de escribir es el del
GRUPO (`grupo_del_profesor`), como en evaluar; el de mirar el estado lo tiene
también el alumnado matriculado, porque la pantalla proyectada es la misma
presentación que ellos pueden abrir, y antes de revelar no enseña respuestas.
"""

import logging
import time

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from clases.models import ClassSession, Enrollment
from martina_bescos_app.users.permisos import es_profesor, grupo_del_profesor

from . import aruco, vivo
from . import tarjetas as tarjetas_pdf
from .composicion import proponer
from .models import Pase, Pregunta
from .views import TAMANO_MAXIMO

logger = logging.getLogger(__name__)


def _pase_del_profesor(request, pk):
    pase = get_object_or_404(Pase.objects.select_related("group", "session"), pk=pk)
    grupo_del_profesor(request.user, pase.group_id)
    return pase


def _pase_visible(request, pk):
    """Profesorado del grupo o alumnado matriculado; el resto, 403 como en la presentación."""
    pase = get_object_or_404(Pase.objects.select_related("group", "session"), pk=pk)
    user = request.user
    if user.is_staff or pase.group.teachers.filter(pk=user.pk).exists():
        return pase
    if Enrollment.objects.filter(user=user, group=pase.group, is_active=True).exists():
        return pase
    raise PermissionDenied("No tienes permiso para ver este pase.")


def _error(mensaje, status=400):
    return JsonResponse({"error": mensaje}, status=status)


# =============================================================================
# CREAR DESDE LA SESIÓN (C479)
# =============================================================================


@login_required
@user_passes_test(es_profesor)
def pase_nuevo(request):
    """`?session=<pk>`: propone la composición de C476 y deja quitar, añadir o
    sustituir antes de guardar. Guardar crea el pase y su elemento de Teoría."""
    session = get_object_or_404(
        ClassSession.objects.select_related("group"),
        pk=request.GET.get("session") or request.POST.get("session"),
        teacher=request.user,
    )
    propuesta = proponer(session.group, session.date)
    propuestas = list(propuesta.preguntas)
    ids_propuestos = {p.pk for p in propuestas}
    otras = [
        p
        for p in Pregunta.objects.filter(estado=Pregunta.ACTIVA).prefetch_related("etiquetas")
        if p.pk not in ids_propuestos
    ]
    error = None
    if request.method == "POST":
        elegidas = [v for v in request.POST.getlist("preguntas") if v.isdigit()]
        activas = {p.pk: p for p in Pregunta.objects.filter(pk__in=elegidas, estado=Pregunta.ACTIVA)}
        preguntas = [activas[int(v)] for v in elegidas if int(v) in activas]
        if not preguntas:
            error = "Elige al menos una pregunta."
        else:
            vivo.crear_desde_sesion(session, preguntas, request.user)
            return redirect(reverse("clases:class_session_edit", args=[session.pk]))
    return render(
        request,
        "preguntas/pase_nuevo.html",
        {
            "session": session,
            "propuestas": propuestas,
            "motivo": propuesta.motivo,
            "conceptos": sorted(propuesta.conceptos),
            "otras": otras,
            "error": error,
        },
    )


@login_required
@user_passes_test(es_profesor)
@require_GET
def tarjetas_grupo(request, group_id):
    """El juego de tarjetas del grupo (C478). Da número a quien no lo tenga."""
    grupo = grupo_del_profesor(request.user, group_id)
    try:
        tarjetas = vivo.tarjetas_de(grupo)
    except ValueError as e:
        return HttpResponse(str(e), status=400)
    respuesta = HttpResponse(tarjetas_pdf.pdf_tarjetas(tarjetas), content_type="application/pdf")
    respuesta["Content-Disposition"] = f'inline; filename="tarjetas-{grupo.pk}.pdf"'
    return respuesta


# =============================================================================
# EN CLASE (C480, C481, C482)
# =============================================================================


@login_required
@require_GET
def pase_estado(request, pk):
    return JsonResponse(vivo.estado_de(_pase_visible(request, pk)))


@login_required
@user_passes_test(es_profesor)
@require_POST
def pase_abrir(request, pk):
    pase = _pase_del_profesor(request, pk)
    if pase.estado == Pase.CERRADO:
        return _error("El pase ya está cerrado.")
    return JsonResponse(vivo.estado_de(vivo.abrir(pase)))


@login_required
@user_passes_test(es_profesor)
@require_POST
def pase_leer(request, pk):
    """Un fotograma (campo `frame`) → lecturas sobre la pregunta en pantalla.

    La imagen se lee en memoria y se descarta (C483): ni disco, ni `Evidencia`,
    ni cuerpo en los logs. Solo se registra cuántos marcadores y cuánto tardó.
    """
    pase = _pase_del_profesor(request, pk)
    if pase.estado != Pase.ABIERTO:
        return _error("El pase no está abierto.")
    fichero = request.FILES.get("frame")
    datos = fichero.read() if fichero is not None else b""
    if not datos:
        return _error("Falta la imagen")
    if len(datos) > TAMANO_MAXIMO:
        return _error("Imagen demasiado grande")
    empieza = time.perf_counter()
    try:
        marcadores = aruco.detectar(datos)
    except ValueError as e:
        return _error(str(e))
    contadas, desconocidas = vivo.registrar(pase, marcadores)
    ms = (time.perf_counter() - empieza) * 1000
    logger.info(
        "preguntas.pase %d: %d marcadores %s, %d contadas, %d desconocidas, %.1f ms",
        pase.pk, len(marcadores), [m["id"] for m in marcadores], contadas, desconocidas, ms,
    )
    estado = vivo.estado_de(pase)
    estado.update(ms=round(ms, 1), leidas=len(marcadores), contadas=contadas)
    return JsonResponse(estado)


@login_required
@user_passes_test(es_profesor)
@require_POST
def pase_revelar(request, pk):
    pase = _pase_del_profesor(request, pk)
    if pase.estado != Pase.ABIERTO:
        return _error("El pase no está abierto.")
    vivo.revelar(pase)
    return JsonResponse(vivo.estado_de(pase))


@login_required
@user_passes_test(es_profesor)
@require_POST
def pase_siguiente(request, pk):
    pase = _pase_del_profesor(request, pk)
    if pase.estado != Pase.ABIERTO:
        return _error("El pase no está abierto.")
    vivo.siguiente(pase)
    return JsonResponse(vivo.estado_de(pase))


@login_required
@user_passes_test(es_profesor)
@require_POST
def pase_cerrar(request, pk):
    pase = _pase_del_profesor(request, pk)
    if pase.estado == Pase.BORRADOR:
        return _error("El pase no se ha empezado.")
    pase = vivo.cerrar(pase)
    estado = vivo.estado_de(pase)
    estado["respuestas"] = pase.respuestas.count()
    return JsonResponse(estado)


# =============================================================================
# LO QUE PINTA LA PRESENTACIÓN
# =============================================================================


def render_pase_en_clase(request, item):
    """El fragmento que `render_item_content` mete en la presentación para un
    elemento cuyo contenido es un `Pase`."""
    pase = item.content_object
    user = request.user
    profesor = es_profesor(user) and (
        user.is_staff or pase.group.teachers.filter(pk=user.pk).exists()
    )
    return render(
        request,
        "preguntas/pase_en_clase.html",
        {"pase": pase, "item": item, "profesor": profesor, "tamano_maximo": TAMANO_MAXIMO},
    )
