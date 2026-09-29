"""Vistas de calificaciones. TINY VIEWS: la lógica vive en `models.py`, `calculo.py` y `estado.py`.

La pantalla es una sola (`registro`), a pantalla completa y pintada por React
(`calificaciones/frontend/`). El resto de vistas son lo que esa pantalla lee y
escribe, más la página del plan, que sigue siendo una plantilla de Django.

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
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from clases.models import Group
from martina_bescos_app.users.permisos import es_profesor, grupo_del_profesor

from . import calculo, estado, ficheros, plantillas
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


def _pide_json(request) -> bool:
    """La pantalla nueva se identifica con esta cabecera; un formulario de los de antes, no."""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


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
def registro(request, group_id):
    """La pantalla de calificaciones: la de `notas`, a pantalla completa.

    No hereda de `base.html`: lleva su propia barra. Los avisos pendientes se
    recogen aquí y viajan en la configuración; si no, el «ya puedes poner notas»
    de `plan_adoptar` aparecería más tarde en una página que no tiene nada que ver.
    """
    group = grupo_del_profesor(request.user, group_id)
    config = {
        "grupo": group.pk,
        "trimestre": _trimestre(request),
        "base": f"/calificaciones/grupo/{group.pk}/",
        # Dónde está esta misma pantalla para otro grupo: `{id}` lo pone el navegador.
        "ruta_grupo": "/calificaciones/grupo/{id}/",
        "inicio": "/calificaciones/",
        "avisos": [str(m) for m in messages.get_messages(request)],
    }
    respuesta = render(request, "calificaciones/registro.html", {"group": group, "config": config})
    respuesta["Cache-Control"] = "no-store"
    return respuesta


@login_required
@user_passes_test(es_profesor)
def estado_json(request, group_id):
    group = grupo_del_profesor(request.user, group_id)
    respuesta = JsonResponse(estado.estado(group, request.user))
    respuesta["Cache-Control"] = "no-store"
    return respuesta


@login_required
@user_passes_test(es_profesor)
def historial_json(request, group_id):
    group = grupo_del_profesor(request.user, group_id)
    respuesta = JsonResponse({"cambios": estado.historial(group)})
    respuesta["Cache-Control"] = "no-store"
    return respuesta


@login_required
@user_passes_test(es_profesor)
@require_POST
def plan_adoptar(request, group_id):
    """El grupo empieza a usar un plan: desde una plantilla, una copia, o uno existente tal cual."""
    group = grupo_del_profesor(request.user, group_id)
    trimestre = _trimestre(request)
    if Plan.para_grupo(group, trimestre):
        messages.info(request, "Este grupo ya tiene plan para ese trimestre.")
        return redirect(f"/calificaciones/grupo/{group.pk}/?t={trimestre}")
    if request.POST.get("plantilla"):
        plan = plantillas.empezar(group, trimestre, request.POST["plantilla"])
        if plan is None:
            raise Http404("No existe esa plantilla para la materia y el curso de este grupo.")
        if _pide_json(request):
            return JsonResponse({"plan": plan.pk})
        messages.success(request, "Listo: ya puedes poner notas. Los instrumentos se cambian en «Plan y reparto».")
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
    if _pide_json(request):
        return JsonResponse({"plan": plan.pk})
    messages.success(request, f"El grupo usa ahora el plan «{plan.nombre}».")
    return redirect(f"/calificaciones/grupo/{group.pk}/?t={trimestre}")


@login_required
@user_passes_test(es_profesor)
@require_POST
def nota_guardar(request, group_id):
    """Autoguardado. Una celda, o varias del mismo alumno de una vez.

    Varias: `prueba` y `valor` repetidos, emparejados por orden. Es lo que manda
    la pantalla cuando se rellena una fila deprisa. O se guardan todas o
    ninguna: se valida todo antes de escribir nada.
    """
    group = grupo_del_profesor(request.user, group_id)
    alumno = _alumno_del_grupo(group, request.POST.get("alumno"))
    ids, textos = request.POST.getlist("prueba"), request.POST.getlist("valor")
    if not ids or len(ids) != len(textos):
        return JsonResponse({"error": "Falta la prueba o la nota"}, status=400)
    celdas = []
    for prueba_id, texto in zip(ids, textos):
        prueba = _prueba_del_grupo(group, prueba_id)
        try:
            valor = _decimal(texto)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        if not prueba.instrumento.admite(valor):
            etiquetas = ", ".join(o["etiqueta"] for o in prueba.instrumento.opciones_normalizadas())
            return JsonResponse({"error": f"Aquí solo vale: {etiquetas}"}, status=400)
        celdas.append((prueba, valor))
    comentario = request.POST.get("comentario")
    with transaction.atomic():
        for prueba, valor in celdas:
            Nota.poner(prueba, alumno, valor, request.user, comentario)
    prueba, valor = celdas[-1]
    plan = prueba.instrumento.plan
    resultado = plan.resultado_de(alumno)
    return JsonResponse(
        {
            "valor": CambioNota.texto(valor),
            "etiqueta": prueba.instrumento.etiqueta_de(valor),
            "instrumento": prueba.instrumento_id,
            "nota_instrumento": _num(resultado.instrumentos.get(prueba.instrumento_id)),
            "trimestre": _num(resultado.trimestre),
            "cualitativa": resultado.cualitativa,
            "faltan": resultado.faltan,
            "alumno": estado.bloque_alumno(group, alumno),
        }
    )


def _num(valor):
    return None if valor is None else f"{valor:.2f}".rstrip("0").rstrip(".")


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
        return JsonResponse({"calificacion": "", "alumno": estado.bloque_alumno(group, alumno)})
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
    return JsonResponse({"calificacion": calificacion, "alumno": estado.bloque_alumno(group, alumno)})


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
def plan_ajustes(request, plan_id):
    """La regla de los huecos, y pasar todo el plan a letras."""
    plan = _plan_del_profesor(request.user, plan_id)
    if "a_letras" in request.POST:
        plan.pasar_a_letras(plantillas.ESCALA_AD)
        messages.success(request, "Todos los instrumentos se califican ahora con A, B, C y D.")
    else:
        plan.hueco_cuenta_cero = request.POST.get("hueco_cuenta_cero") == "on"
        plan.save(update_fields=["hueco_cuenta_cero"])
        if plan.hueco_cuenta_cero:
            messages.success(request, "Una celda vacía cuenta como 0.")
        else:
            messages.success(request, "Una celda vacía no cuenta: la media se hace con el resto.")
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
    escala = request.POST.get("escala") or Instrumento.ESCALA_NUMERICA
    try:
        opciones = _opciones(request.POST.get("opciones"))
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("calificaciones:plan", plan_id=plan.pk)
    if escala == Instrumento.ESCALA_OPCIONES and not opciones:
        # Una lista de opciones sin opciones: se le da la escala de letras del curso.
        opciones = [dict(o) for o in plantillas.ESCALA_AD]
    Instrumento.objects.create(
        plan=plan,
        nombre=nombre,
        abreviatura=(request.POST.get("abreviatura") or "")[:12],
        orden=plan.instrumentos.count(),
        escala=escala,
        opciones=opciones,
    )
    messages.success(request, f"Instrumento «{nombre}» creado. Ahora repártele porcentaje.")
    return redirect("calificaciones:plan", plan_id=plan.pk)


def _opciones(texto) -> list:
    """`Etiqueta=valor` por línea, o vacío. `ValueError` si dos opciones se pisan."""
    salida = []
    for linea in (texto or "").splitlines():
        if "=" not in linea:
            continue
        etiqueta, valor = linea.rsplit("=", 1)
        try:
            salida.append({"etiqueta": etiqueta.strip(), "valor": float(valor.strip().replace(",", "."))})
        except ValueError:
            continue
    return Instrumento.limpiar_opciones(salida)


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
        try:
            instrumento.opciones = _opciones(request.POST.get("opciones"))
        except ValueError as e:
            messages.error(request, f"{instrumento.nombre}: {e}. No se ha guardado nada.")
            return redirect("calificaciones:plan", plan_id=plan.pk)
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
    if _pide_json(request):
        return JsonResponse({"id": prueba.pk, "nombre": prueba.nombre, "activa": prueba.activa})
    return redirect("calificaciones:plan", plan_id=plan.pk)


# =============================================================================
# EVIDENCIAS
# =============================================================================


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
        # Qué es lo decide la extensión, no lo que diga el navegador.
        evidencia.tipo = ficheros.clasificar(tipo, fichero.name)
        if evidencia.tipo is None:
            return JsonResponse({"error": f"Ese fichero no es de tipo «{tipo}»"}, status=400)
        evidencia.nombre_original = Path(fichero.name).name[:255]
        evidencia.tamano = fichero.size
        evidencia.tipo_mime = ficheros.tipo_de_contenido(evidencia.tipo, fichero.name) or ""
        evidencia.archivo = fichero
        if evidencia.tipo == Evidencia.VIDEO:
            evidencia.estado = Evidencia.PENDIENTE
    evidencia.save()
    if evidencia.tipo == Evidencia.VIDEO:
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
            "evidencia": estado.evidencia_json(evidencia),
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
    return ficheros.servir(request, fichero, evidencia.tipo, evidencia.nombre_original)


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
@require_POST
def cambio_revertir(request, pk):
    cambio = get_object_or_404(
        CambioNota.objects.select_related("nota__prueba__instrumento__plan"), pk=pk
    )
    plan = _plan_del_profesor(request.user, cambio.nota.prueba.instrumento.plan_id)
    cambio.revertir(request.user)
    if _pide_json(request):
        # El grupo desde el que se mira; si el plan es de varios, el primero del profesor.
        grupos = plan.groups.all() if request.user.is_staff else plan.groups.filter(teachers=request.user)
        group = grupos.filter(pk=request.POST.get("grupo")).first() or grupos.first()
        return JsonResponse({"alumno": estado.bloque_alumno(group, cambio.nota.alumno)})
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
