"""Vistas de calificaciones. TINY VIEWS: la lógica vive en `models.py` y `calculo.py`.

Todas exigen `es_profesor`, y cada grupo pasa por `grupo_del_profesor`, que
devuelve 404 y no 403 a propósito (un 403 confirma que el grupo existe). Un
plan se puede editar si es de alguno de tus grupos; para adoptarlo o copiarlo
basta con que sea de tu materia y tu curso.
"""

from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from clases.models import Group
from martina_bescos_app.users.permisos import es_profesor, grupo_del_profesor

from . import calculo
from .models import (
    CambioNota,
    Evidencia,
    Instrumento,
    Nota,
    NotaManual,
    Plan,
    Prueba,
    alumnos_del_grupo,
)

TIPO_MIME = {
    ".webm": "video/webm",
    ".mp4": "video/mp4",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
}
TAMANO_MAXIMO = 50 * 1024 * 1024


def _trimestre(request) -> int:
    try:
        t = int(request.GET.get("t", 1))
    except ValueError:
        t = 1
    return t if t in (1, 2, 3) else 1


def _plan_del_profesor(user, plan_id) -> Plan:
    plan = Plan.del_profesor(user).filter(pk=plan_id).select_related("marco").first()
    if plan is None:
        raise Http404("No existe ese plan o no es de ninguno de tus grupos.")
    return plan


def _decimal(texto) -> Decimal | None:
    """`''` es «sin nota»; cualquier otra cosa, un número entre 0 y 10 o ValueError."""
    texto = (texto or "").strip().replace(",", ".")
    if texto == "":
        return None
    try:
        valor = Decimal(texto)
    except InvalidOperation as e:
        raise ValueError("No es un número") from e
    if not (0 <= valor <= 10):
        raise ValueError("La nota va de 0 a 10")
    return valor.quantize(Decimal("0.01"))


def _alumno_del_grupo(group, alumno_id):
    alumno = alumnos_del_grupo(group).filter(pk=alumno_id).first()
    if alumno is None:
        raise Http404("Ese alumno no está en el grupo.")
    return alumno


def _prueba_del_grupo(group, prueba_id) -> Prueba:
    prueba = (
        Prueba.objects.filter(pk=prueba_id, instrumento__plan__groups=group)
        .select_related("instrumento__plan")
        .first()
    )
    if prueba is None:
        raise Http404("Esa prueba no es de este grupo.")
    return prueba


# =============================================================================
# GRUPOS Y CUADRO
# =============================================================================


@login_required
@user_passes_test(es_profesor)
def index(request):
    grupos = Group.del_profesor(request.user).select_related("subject").prefetch_related(
        "planes_calificacion"
    )
    return render(request, "calificaciones/index.html", {"grupos": grupos})


@login_required
@user_passes_test(es_profesor)
def cuadro(request, group_id):
    group = grupo_del_profesor(request.user, group_id)
    trimestre = _trimestre(request)
    plan = Plan.para_grupo(group, trimestre)
    contexto = {
        "group": group,
        "trimestre": trimestre,
        "trimestres": [1, 2, 3],
        "plan": plan,
    }
    if plan is None:
        contexto["elegibles"] = Plan.elegibles_para(group, trimestre)
        contexto["copiables"] = Plan.objects.filter(
            marco__subject=group.subject, marco__academic_year=group.academic_year
        ).select_related("marco")
        return render(request, "calificaciones/cuadro.html", contexto)

    alumnos = list(alumnos_del_grupo(group))
    contexto.update(plan.filas_cuadro(group, alumnos))
    contexto["manuales"] = {
        m.alumno_id: m
        for m in NotaManual.objects.filter(group=group, alumno__in=alumnos, ambito=str(trimestre))
    }
    contexto["cualitativas"] = NotaManual.CALIFICACIONES
    return render(request, "calificaciones/cuadro.html", contexto)


@login_required
@user_passes_test(es_profesor)
@require_POST
def plan_adoptar(request, group_id):
    """El grupo empieza a usar un plan: uno existente tal cual, o una copia."""
    group = grupo_del_profesor(request.user, group_id)
    trimestre = _trimestre(request)
    if Plan.para_grupo(group, trimestre):
        messages.info(request, "Este grupo ya tiene plan para ese trimestre.")
        return redirect(f"/calificaciones/grupo/{group.pk}/?t={trimestre}")
    if request.POST.get("copiar_de"):
        origen = get_object_or_404(
            Plan, pk=request.POST["copiar_de"], marco__subject=group.subject
        )
        nombre = (request.POST.get("nombre") or "").strip() or f"{group.name} · {trimestre}ª ev."
        plan = origen.copiar(trimestre, nombre)
    else:
        plan = get_object_or_404(Plan.elegibles_para(group, trimestre), pk=request.POST.get("plan_id"))
    plan.groups.add(group)
    messages.success(request, f"El grupo usa ahora el plan «{plan.nombre}».")
    return redirect(f"/calificaciones/grupo/{group.pk}/?t={trimestre}")


@login_required
@user_passes_test(es_profesor)
@require_POST
def nota_guardar(request, group_id):
    """Autoguardado de una celda. Devuelve la fila recalculada."""
    group = grupo_del_profesor(request.user, group_id)
    prueba = _prueba_del_grupo(group, request.POST.get("prueba"))
    alumno = _alumno_del_grupo(group, request.POST.get("alumno"))
    try:
        valor = _decimal(request.POST.get("valor"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    comentario = request.POST.get("comentario")
    Nota.poner(prueba, alumno, valor, request.user, comentario)
    plan = prueba.instrumento.plan
    resultado = plan.resultado_de(alumno)
    return JsonResponse(
        {
            "valor": CambioNota.texto(valor),
            "instrumento": prueba.instrumento_id,
            "nota_instrumento": _num(resultado.instrumentos.get(prueba.instrumento_id)),
            "trimestre": _num(resultado.trimestre),
            "cualitativa": resultado.cualitativa,
            "faltan": resultado.faltan,
        }
    )


def _num(valor):
    return None if valor is None else f"{valor:.2f}".rstrip("0").rstrip(".")


@login_required
@user_passes_test(es_profesor)
def panel(request, group_id, instrumento_id, alumno_id):
    """Las pruebas de un instrumento para un alumno, con sus evidencias."""
    group = grupo_del_profesor(request.user, group_id)
    instrumento = get_object_or_404(Instrumento, pk=instrumento_id, plan__groups=group)
    alumno = _alumno_del_grupo(group, alumno_id)
    pruebas = list(instrumento.pruebas.all())
    notas = {n.prueba_id: n for n in Nota.objects.filter(prueba__in=pruebas, alumno=alumno)}
    evidencias = Evidencia.objects.filter(prueba__in=pruebas, alumno=alumno).select_related("prueba")
    return render(
        request,
        "calificaciones/partials/panel.html",
        {
            "group": group,
            "instrumento": instrumento,
            "alumno": alumno,
            "filas": [(p, notas.get(p.pk)) for p in pruebas],
            "evidencias": evidencias,
            "opciones": instrumento.opciones_normalizadas(),
        },
    )


@login_required
@user_passes_test(es_profesor)
@require_POST
def nota_manual_guardar(request, group_id):
    group = grupo_del_profesor(request.user, group_id)
    alumno = _alumno_del_grupo(group, request.POST.get("alumno"))
    ambito = request.POST.get("ambito", "")
    calificacion = request.POST.get("calificacion", "")
    if ambito not in dict(NotaManual.AMBITOS):
        return JsonResponse({"error": "Ámbito desconocido"}, status=400)
    if calificacion == "":
        NotaManual.objects.filter(group=group, alumno=alumno, ambito=ambito).delete()
        return JsonResponse({"calificacion": ""})
    if calificacion not in calculo.CUALITATIVAS:
        return JsonResponse({"error": "Calificación desconocida"}, status=400)
    NotaManual.objects.update_or_create(
        group=group,
        alumno=alumno,
        ambito=ambito,
        defaults={
            "calificacion": calificacion,
            "motivo": request.POST.get("motivo", ""),
            "updated_by": request.user,
        },
    )
    return JsonResponse({"calificacion": calificacion})


# =============================================================================
# PLAN: INSTRUMENTOS Y REPARTO
# =============================================================================


@login_required
@user_passes_test(es_profesor)
def plan(request, plan_id):
    plan = _plan_del_profesor(request.user, plan_id)
    cuadre = plan.cuadre()
    instrumentos = list(plan.instrumentos.prefetch_related("pruebas", "repartos"))
    return render(
        request,
        "calificaciones/plan.html",
        {
            "plan": plan,
            "cuadre": cuadre,
            "instrumentos": instrumentos,
            "grupos": plan.groups.all(),
            "escalas": Instrumento.ESCALAS,
            "agregaciones": Instrumento.AGREGACIONES,
            "celdas_json": json.dumps(
                {f"{c}-{i}": str(p) for (c, i), p in plan.celdas().items()}
            ),
            "pesos_json": json.dumps({c.pk: str(c.peso) for c in cuadre["criterios"]}),
        },
    )


@login_required
@user_passes_test(es_profesor)
@require_POST
def reparto_guardar(request, plan_id):
    """Sustituye el reparto entero. Las celdas llegan como `celda-<criterio>-<instrumento>`."""
    plan = _plan_del_profesor(request.user, plan_id)
    criterios = set(plan.marco.criterios.values_list("pk", flat=True))
    instrumentos = set(plan.instrumentos.values_list("pk", flat=True))
    valores = {}
    for clave, texto in request.POST.items():
        if not clave.startswith("celda-"):
            continue
        try:
            _, c, i = clave.split("-")
            c, i = int(c), int(i)
            porcentaje = Decimal((texto or "0").replace(",", ".") or "0")
        except (ValueError, InvalidOperation):
            return HttpResponse("Celda inválida", status=400)
        if c in criterios and i in instrumentos and porcentaje > 0:
            valores[(c, i)] = porcentaje.quantize(Decimal("0.01"))
    plan.guardar_reparto(valores)
    cuadre = plan.cuadre()
    if cuadre["cuadra"]:
        messages.success(request, "Reparto guardado. Cuadra.")
    else:
        messages.warning(request, f"Reparto guardado, pero no cuadra: suma {cuadre['total']} %.")
    return redirect("calificaciones:plan", plan_id=plan.pk)


@login_required
@user_passes_test(es_profesor)
@require_POST
def instrumento_crear(request, plan_id):
    plan = _plan_del_profesor(request.user, plan_id)
    nombre = (request.POST.get("nombre") or "").strip()
    if not nombre:
        messages.error(request, "El instrumento necesita un nombre.")
        return redirect("calificaciones:plan", plan_id=plan.pk)
    Instrumento.objects.create(
        plan=plan,
        nombre=nombre,
        abreviatura=(request.POST.get("abreviatura") or "")[:12],
        orden=plan.instrumentos.count(),
        escala=request.POST.get("escala") or Instrumento.ESCALA_NUMERICA,
        opciones=_opciones(request.POST.get("opciones")),
    )
    messages.success(request, f"Instrumento «{nombre}» creado. Ahora repártele porcentaje.")
    return redirect("calificaciones:plan", plan_id=plan.pk)


def _opciones(texto) -> list:
    """`Etiqueta=valor` por línea, o vacío."""
    salida = []
    for linea in (texto or "").splitlines():
        if "=" not in linea:
            continue
        etiqueta, valor = linea.rsplit("=", 1)
        try:
            salida.append({"etiqueta": etiqueta.strip(), "valor": float(valor.strip().replace(",", "."))})
        except ValueError:
            continue
    return salida


@login_required
@user_passes_test(es_profesor)
@require_POST
def instrumento_editar(request, pk):
    instrumento = get_object_or_404(Instrumento, pk=pk)
    plan = _plan_del_profesor(request.user, instrumento.plan_id)
    if "borrar" in request.POST:
        nombre = instrumento.nombre
        instrumento.delete()
        messages.success(request, f"Instrumento «{nombre}» borrado, con sus notas.")
        return redirect("calificaciones:plan", plan_id=plan.pk)
    instrumento.nombre = (request.POST.get("nombre") or instrumento.nombre).strip()
    instrumento.abreviatura = (request.POST.get("abreviatura") or instrumento.abreviatura)[:12]
    if request.POST.get("escala") in dict(Instrumento.ESCALAS):
        instrumento.escala = request.POST["escala"]
    if request.POST.get("agregacion") in dict(Instrumento.AGREGACIONES):
        instrumento.agregacion = request.POST["agregacion"]
    if "opciones" in request.POST:
        instrumento.opciones = _opciones(request.POST.get("opciones"))
    try:
        instrumento.orden = int(request.POST.get("orden", instrumento.orden))
    except ValueError:
        pass
    instrumento.save()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("calificaciones:plan", plan_id=plan.pk)


@login_required
@user_passes_test(es_profesor)
@require_POST
def prueba_crear(request, instrumento_id):
    instrumento = get_object_or_404(Instrumento, pk=instrumento_id)
    plan = _plan_del_profesor(request.user, instrumento.plan_id)
    nombre = (request.POST.get("nombre") or "").strip() or f"{instrumento.nombre} {instrumento.pruebas.count() + 1}"
    prueba = Prueba(instrumento=instrumento, nombre=nombre)
    if request.POST.get("fecha"):
        prueba.fecha = request.POST["fecha"]
    prueba.save()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"id": prueba.pk, "nombre": prueba.nombre, "instrumento": instrumento.pk})
    destino = request.POST.get("next") or f"/calificaciones/plan/{plan.pk}/"
    return redirect(destino)


@login_required
@user_passes_test(es_profesor)
@require_POST
def prueba_editar(request, pk):
    prueba = get_object_or_404(Prueba.objects.select_related("instrumento"), pk=pk)
    plan = _plan_del_profesor(request.user, prueba.instrumento.plan_id)
    if "borrar" in request.POST:
        if prueba.instrumento.pruebas.count() == 1:
            messages.error(request, "Un instrumento necesita al menos una prueba.")
        else:
            prueba.delete()
            messages.success(request, "Prueba borrada, con sus notas y evidencias.")
        return redirect("calificaciones:plan", plan_id=plan.pk)
    prueba.nombre = (request.POST.get("nombre") or prueba.nombre).strip()
    if request.POST.get("fecha"):
        prueba.fecha = request.POST["fecha"]
    prueba.activa = request.POST.get("activa", "on") == "on"
    prueba.save()
    return redirect("calificaciones:plan", plan_id=plan.pk)


# =============================================================================
# MODO CLASE Y EVIDENCIAS
# =============================================================================


@login_required
@user_passes_test(es_profesor)
def clase(request, group_id):
    group = grupo_del_profesor(request.user, group_id)
    trimestre = _trimestre(request)
    plan = Plan.para_grupo(group, trimestre)
    if plan is None:
        messages.info(request, "Este grupo aún no tiene plan de calificación para ese trimestre.")
        return redirect(f"/calificaciones/grupo/{group.pk}/?t={trimestre}")
    pruebas = list(
        Prueba.objects.filter(instrumento__plan=plan, activa=True)
        .select_related("instrumento")
        .order_by("instrumento__orden", "fecha", "pk")
    )
    prueba = None
    if request.GET.get("prueba"):
        prueba = next((p for p in pruebas if str(p.pk) == request.GET["prueba"]), None)
    if prueba is None and pruebas:
        # La última en la que se puso una nota, o la primera.
        ultima = (
            Nota.objects.filter(prueba__in=pruebas).order_by("-updated_at").values_list("prueba_id", flat=True).first()
        )
        prueba = next((p for p in pruebas if p.pk == ultima), pruebas[0])
    alumnos = list(alumnos_del_grupo(group))
    notas = prueba.notas_de(alumnos) if prueba else {}
    recuento = {}
    if prueba:
        for fila in (
            Evidencia.objects.filter(prueba=prueba, alumno__in=alumnos)
            .values("alumno_id")
            .annotate(n=Count("id"))
        ):
            recuento[fila["alumno_id"]] = fila["n"]
    return render(
        request,
        "calificaciones/clase.html",
        {
            "group": group,
            "trimestre": trimestre,
            "plan": plan,
            "pruebas": pruebas,
            "prueba": prueba,
            "instrumentos": plan.instrumentos.all(),
            "alumnos": [(a, notas.get(a.pk), recuento.get(a.pk, 0)) for a in alumnos],
            "opciones": prueba.instrumento.opciones_normalizadas() if prueba else [],
        },
    )


@login_required
@user_passes_test(es_profesor)
@require_POST
def evidencia_subir(request, group_id):
    group = grupo_del_profesor(request.user, group_id)
    prueba = _prueba_del_grupo(group, request.POST.get("prueba"))
    alumno = _alumno_del_grupo(group, request.POST.get("alumno"))
    tipo = request.POST.get("tipo", "")
    if tipo not in dict(Evidencia.TIPOS):
        return JsonResponse({"error": "Tipo desconocido"}, status=400)
    evidencia = Evidencia(prueba=prueba, alumno=alumno, tipo=tipo, created_by=request.user)
    if tipo in (Evidencia.TEXTO, Evidencia.ENLACE):
        evidencia.texto = (request.POST.get("texto") or "").strip()
        if not evidencia.texto:
            return JsonResponse({"error": "Falta el texto"}, status=400)
    else:
        fichero = request.FILES.get("archivo")
        if fichero is None:
            return JsonResponse({"error": "Falta el archivo"}, status=400)
        if fichero.size > TAMANO_MAXIMO:
            return JsonResponse({"error": "Archivo demasiado grande (máximo 50 MB)"}, status=400)
        evidencia.tipo_mime = fichero.content_type or ""
        evidencia.archivo = fichero
        if tipo == Evidencia.VIDEO:
            evidencia.estado = Evidencia.PENDIENTE
    evidencia.save()
    if tipo == Evidencia.VIDEO:
        from .tasks import comprimir_video

        comprimir_video(evidencia.pk)
    return JsonResponse(
        {
            "id": evidencia.pk,
            "tipo": evidencia.tipo,
            "icono": evidencia.icono,
            "url": f"/calificaciones/evidencia/{evidencia.pk}/",
            "texto": evidencia.texto,
            "total": Evidencia.objects.filter(prueba=prueba, alumno=alumno).count(),
        }
    )


def _evidencia_del_profesor(user, pk) -> Evidencia:
    evidencia = (
        Evidencia.objects.filter(pk=pk)
        .select_related("prueba__instrumento__plan", "alumno")
        .first()
    )
    if evidencia is None:
        raise Http404("No existe esa evidencia.")
    plan = evidencia.prueba.instrumento.plan
    if user.is_staff or plan.groups.filter(teachers=user).exists():
        return evidencia
    raise Http404("No existe esa evidencia.")


@login_required
@user_passes_test(es_profesor)
def evidencia_ver(request, pk):
    """El fichero, solo para el profesorado del grupo. nginx tiene cerrado `/media/calificaciones/`."""
    evidencia = _evidencia_del_profesor(request.user, pk)
    fichero = evidencia.fichero
    if not fichero:
        raise Http404("Esta evidencia no tiene fichero.")
    extension = Path(fichero.name).suffix.lower()
    tipo = evidencia.tipo_mime or TIPO_MIME.get(extension, "application/octet-stream")
    if evidencia.archivo_comprimido:
        tipo = "video/mp4"
    respuesta = FileResponse(fichero.open("rb"), content_type=tipo)
    respuesta["Cache-Control"] = "private, max-age=3600"
    return respuesta


@login_required
@user_passes_test(es_profesor)
@require_POST
def evidencia_borrar(request, pk):
    evidencia = _evidencia_del_profesor(request.user, pk)
    prueba, alumno = evidencia.prueba, evidencia.alumno
    evidencia.delete()
    return JsonResponse({"ok": True, "total": Evidencia.objects.filter(prueba=prueba, alumno=alumno).count()})


# =============================================================================
# HISTORIAL Y EXPORTACIÓN
# =============================================================================


@login_required
@user_passes_test(es_profesor)
def historial(request, group_id):
    group = grupo_del_profesor(request.user, group_id)
    cambios = (
        CambioNota.objects.filter(nota__prueba__instrumento__plan__groups=group)
        .select_related("nota__alumno", "nota__prueba__instrumento", "user", "revertido_de")
        .distinct()
    )
    alumno_id = request.GET.get("alumno")
    if alumno_id:
        cambios = cambios.filter(nota__alumno_id=alumno_id)
    return render(
        request,
        "calificaciones/historial.html",
        {
            "group": group,
            "cambios": cambios[:300],
            "alumnos": alumnos_del_grupo(group),
            "alumno_id": alumno_id,
        },
    )


@login_required
@user_passes_test(es_profesor)
@require_POST
def cambio_revertir(request, pk):
    cambio = get_object_or_404(
        CambioNota.objects.select_related("nota__prueba__instrumento__plan"), pk=pk
    )
    _plan_del_profesor(request.user, cambio.nota.prueba.instrumento.plan_id)
    cambio.revertir(request.user)
    messages.success(request, "Nota devuelta a su valor anterior.")
    return redirect(request.POST.get("next") or "/calificaciones/")


@login_required
@user_passes_test(es_profesor)
@require_http_methods(["GET"])
def exportar(request, group_id):
    """CSV por criterio (lo que pide la hoja del departamento) o por instrumento."""
    group = grupo_del_profesor(request.user, group_id)
    trimestre = _trimestre(request)
    plan = Plan.para_grupo(group, trimestre)
    if plan is None:
        raise Http404("Sin plan para ese trimestre.")
    por = request.GET.get("por", "criterio")
    alumnos = list(alumnos_del_grupo(group))
    resultados = plan.resultados(alumnos)
    columnas = (
        list(plan.marco.criterios.all()) if por == "criterio" else list(plan.instrumentos.all())
    )
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    nombre = f"{group.name}_{trimestre}ev_por_{por}.csv".replace(" ", "_")
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    respuesta.write("﻿")
    escritor = csv.writer(respuesta, delimiter=";")
    cabecera = ["Alumno"] + [
        (c.codigo if por == "criterio" else c.nombre) for c in columnas
    ] + ["Nota", "Calificación"]
    escritor.writerow(cabecera)
    for alumno in alumnos:
        r = resultados[alumno.pk]
        valores = r.criterios if por == "criterio" else r.instrumentos
        escritor.writerow(
            [alumno.name or alumno.email]
            + [_csv(valores.get(c.pk)) for c in columnas]
            + [_csv(r.trimestre), r.cualitativa]
        )
    return respuesta


def _csv(valor):
    return "" if valor is None else f"{valor:.2f}".replace(".", ",")
