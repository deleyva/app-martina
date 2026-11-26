"""Pantallas de la banda del grupo (fase 92): la rejilla del curso, la hoja de la
pared y la banda de hoy en la clase.

Toda regla vive en `clases/banda.py`; aquí solo se comprueba quién es y se
traduce. La rejilla son formularios corrientes que vuelven a la rejilla; la
banda de hoy habla JSON con el panel de `present.html`.
"""

import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from clases import banda as bandas
from clases.models import BandaDeGrupo
from clases.models import BandaVersion
from clases.models import ClassSessionItem
from clases.views_plano import _sesion_del_profesor
from martina_bescos_app.users.permisos import es_profesor
from martina_bescos_app.users.permisos import grupo_del_profesor


def _volver(group, turno=None):
    url = reverse("clases:banda_rejilla", args=[group.pk])
    return redirect(f"{url}#turno-{turno}" if turno else url)


def _banda_o_404(grupo):
    banda = bandas.banda_de(grupo)
    if banda is None:
        raise Http404("Este grupo aún no tiene banda")
    return banda


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ValidationError("Falta un número") from None


def _lista(texto):
    return [p for p in (texto or "").split(",") if p]


def _avisar(request, e):
    for m in e.messages:
        messages.error(request, m)


# -----------------------------------------------------------------------------
# La rejilla del curso
# -----------------------------------------------------------------------------


@login_required
@user_passes_test(es_profesor)
@require_GET
def banda_rejilla(request, group_id):
    grupo = grupo_del_profesor(request.user, group_id)
    banda = bandas.banda_de(grupo)
    contexto = {"group": grupo, "banda": banda, "puestos": bandas.PUESTOS.values()}
    if banda is not None:
        datos = bandas.rejilla(banda)
        contexto.update({
            "datos": datos,
            "filas": [
                {
                    "cabecera": datos["filas"][i] if i < len(datos["filas"]) else None,
                    "casillas": [
                        (col, col["casillas"][i] if i < len(col["casillas"]) else None)
                        for col in datos["columnas"]
                    ],
                }
                for i in range(datos["max_filas"])
            ],
            "puestos_config": [(p, banda.puestos.count(p.clave)) for p in bandas.PUESTOS.values()],
            # Fase 98: los chips de la tabla de alumnos son los puestos del grupo, más los que alguien ya tenga.
            "puestos_chips": [
                bandas.PUESTOS[c] for c in dict.fromkeys(
                    list(banda.puestos) + [p for a in datos["alumnos"] for p in a["puestos"] + a["no"]]
                )
            ],
            "anillos": [("rota", "Rota"), ("fijo", "Fijo"), ("fuera", "No entra")],
            "papeles_resto": [bandas.PAPELES[c] for c in bandas.PREFERIBLES],
            "versiones": bandas.versiones(banda),
            "modos": BandaDeGrupo.MODOS,
            "cuentas": BandaDeGrupo.CUENTAS,
            "alumnos_dialogo": [
                {"id": a["id"], "nombre": a["nombre"], "turnos": len(a["turnos"])} for a in datos["alumnos"]
            ],
        })
    return render(request, "clases/banda/rejilla.html", contexto)


@login_required
@user_passes_test(es_profesor)
@require_POST
def banda_crear(request, group_id):
    grupo = grupo_del_profesor(request.user, group_id)
    if bandas.banda_de(grupo) is None:
        bandas.crear(grupo, autor=request.user)
    return _volver(grupo)


@login_required
@user_passes_test(es_profesor)
@require_POST
def banda_configurar(request, group_id):
    grupo = grupo_del_profesor(request.user, group_id)
    banda = _banda_o_404(grupo)
    puestos = []
    try:
        for clave in bandas.PUESTOS:
            puestos += [clave] * _entero(request.POST.get(f"plazas_{clave}", 0) or 0)
        bandas.configurar(
            banda,
            modo=request.POST.get("modo"),
            puestos=puestos,
            sesiones_por_turno=request.POST.get("sesiones_por_turno"),
            turnos=request.POST.get("turnos"),
            empieza=date.fromisoformat(request.POST.get("empieza") or ""),
            cuenta=request.POST.get("cuenta"),
            autor=request.user,
        )
        messages.success(request, "Configuración guardada.")
    except ValueError:
        messages.error(request, "La fecha de inicio no es válida.")
    except ValidationError as e:
        _avisar(request, e)
    return _volver(grupo)


@login_required
@user_passes_test(es_profesor)
@require_POST
def banda_alumnos(request, group_id):
    """La tabla de alumnos (fases 98 y 117). Por alumno:

    - `anillo_<id>`: rota | fijo | fuera.
    - `fijo_<id>`: sus puestos de fijo, separados por comas y en orden de preferencia.
    - `no_<id>`: los puestos que nunca toca (solo cuenta en «rota»), separados por comas.
    - `resto_<id>`: ukelele | xilofono, lo que toca cuando no tiene puesto.

    Se sigue entendiendo el formulario anterior (`veto`, `puestos_<id>` y
    `orden_<id>`), por si queda una pestaña abierta de antes del despliegue.
    """
    grupo = grupo_del_profesor(request.user, group_id)
    banda = _banda_o_404(grupo)
    alumnos = {}
    for clave, valor in request.POST.items():
        if not clave.startswith("anillo_") or not clave[7:].isdigit():
            continue
        alumno = clave[7:]
        marcados = request.POST.getlist(f"puestos_{alumno}")
        orden = [p for p in (request.POST.get(f"orden_{alumno}") or "").split(",") if p in marcados]
        puestos = orden + [p for p in marcados if p not in orden]
        fijo = _lista(request.POST.get(f"fijo_{alumno}")) or (puestos if valor == "fijo" else [])
        no = _lista(request.POST.get(f"no_{alumno}")) or (puestos if valor == "veto" else [])
        alumnos[alumno] = {
            "anillo": "rota" if valor == "veto" else valor,
            "puestos": fijo if valor == "fijo" else [],
            "no": no if valor in ("rota", "veto") else [],
            "resto": request.POST.get(f"resto_{alumno}") or None,
        }
    try:
        banda = bandas.configurar_alumnos(banda, alumnos, autor=request.user)
        messages.success(
            request,
            "Guardado. Los turnos que no han empezado se han vuelto a generar."
            if banda.regenerada
            else "Guardado. Los turnos no se han movido.",
        )
    except ValidationError as e:
        _avisar(request, e)
    return _volver(grupo)


@login_required
@user_passes_test(es_profesor)
@require_POST
def banda_generar(request, group_id):
    grupo = grupo_del_profesor(request.user, group_id)
    banda = _banda_o_404(grupo)
    try:
        bandas.generar(banda, autor=request.user, motivo=request.POST.get("motivo", ""))
        messages.success(request, "Curso generado. Lo fijado y lo ya jugado no se ha movido.")
    except ValidationError as e:
        _avisar(request, e)
    return _volver(grupo)


@login_required
@user_passes_test(es_profesor)
@require_POST
def banda_casilla(request, group_id):
    """Pone a un alumno en una plaza (o la vacía, sin alumno) y la deja fijada."""
    grupo = grupo_del_profesor(request.user, group_id)
    banda = _banda_o_404(grupo)
    turno = None
    try:
        turno = _entero(request.POST.get("turno"))
        plaza = _entero(request.POST.get("plaza"))
        if request.POST.get("accion") == "soltar":
            bandas.soltar(banda, turno, plaza, autor=request.user)
        else:
            alumno = request.POST.get("alumno")
            bandas.poner(banda, turno, plaza, _entero(alumno) if alumno else None, autor=request.user)
    except ValidationError as e:
        _avisar(request, e)
    return _volver(grupo, turno)


@login_required
@user_passes_test(es_profesor)
@require_POST
def banda_ajustar(request, group_id):
    grupo = grupo_del_profesor(request.user, group_id)
    banda = _banda_o_404(grupo)
    bandas.ajustar(banda, 1 if request.POST.get("hacia") == "adelante" else -1, autor=request.user)
    return _volver(grupo)


@login_required
@user_passes_test(es_profesor)
@require_POST
def banda_restaurar(request, group_id, version_id):
    grupo = grupo_del_profesor(request.user, group_id)
    banda = _banda_o_404(grupo)
    version = get_object_or_404(BandaVersion, pk=version_id, banda=banda)
    try:
        bandas.restaurar(version, autor=request.user)
        messages.success(request, "Vuelta a la versión elegida. Lo jugado desde entonces se queda como está.")
    except ValidationError as e:
        _avisar(request, e)
    return _volver(grupo)


@login_required
@user_passes_test(es_profesor)
@require_GET
def banda_hoja(request, group_id):
    """La hoja A4 para la pared: las reglas, la tabla y la lista de cada alumno."""
    grupo = grupo_del_profesor(request.user, group_id)
    banda = _banda_o_404(grupo)
    datos = bandas.rejilla(banda)
    return render(request, "clases/banda/hoja.html", {"group": grupo, "banda": banda, "datos": datos})


# -----------------------------------------------------------------------------
# La banda de hoy, desde la clase
# -----------------------------------------------------------------------------


@login_required
@user_passes_test(es_profesor)
@require_GET
def banda_hoy(request, pk):
    session = _sesion_del_profesor(request, pk)
    return JsonResponse(_hoy(session, _item_de(session, request.GET.get("item"))))


def _item_de(session, pk):
    """El elemento de ESTA sesión que está en pantalla, o None."""
    if isinstance(pk, bool) or not str(pk or "").isdigit():
        return None
    return ClassSessionItem.objects.filter(session=session, pk=int(pk)).select_related("source_page").first()


def _hoy(session, item):
    datos = bandas.banda_de_hoy(session, item)
    datos["url_rejilla"] = reverse("clases:banda_rejilla", args=[session.group_id])
    return datos


@login_required
@user_passes_test(es_profesor)
@require_POST
def banda_hoy_resto(request, pk):
    """Cuerpo JSON: {item, alumno, papel}. `papel` null devuelve al alumno a lo que prefiere;
    `alumno` y `papel` null, a todos (fase 117)."""
    session = _sesion_del_profesor(request, pk)
    try:
        cuerpo = json.loads(request.body or b"{}")
        if not isinstance(cuerpo, dict):
            raise ValidationError("El cuerpo tiene que ser un objeto")
        item = _item_de(session, cuerpo.get("item"))
        bandas.apuntar_resto(session, item, cuerpo.get("alumno"), cuerpo.get("papel"))
    except ValueError:
        return JsonResponse({"errores": ["El cuerpo no es JSON"]}, status=422)
    except ValidationError as e:
        return JsonResponse({"errores": e.messages}, status=422)
    return JsonResponse(_hoy(session, item))


@login_required
@user_passes_test(es_profesor)
@require_POST
def banda_hoy_cambio(request, pk):
    """Cuerpo JSON: {plaza, alumno}. `alumno` null devuelve la plaza a su titular."""
    session = _sesion_del_profesor(request, pk)
    try:
        cuerpo = json.loads(request.body or b"{}")
        alumno = cuerpo.get("alumno")
        if alumno is not None and (isinstance(alumno, bool) or not isinstance(alumno, int)):
            raise ValidationError("El alumno tiene que ser un id")
        bandas.cambiar_hoy(session, cuerpo.get("plaza"), alumno)
    except ValueError:
        return JsonResponse({"errores": ["El cuerpo no es JSON"]}, status=422)
    except ValidationError as e:
        return JsonResponse({"errores": e.messages}, status=422)
    return JsonResponse(_hoy(session, _item_de(session, cuerpo.get("item"))))
