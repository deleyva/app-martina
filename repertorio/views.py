"""Pantalla del catálogo. Delgada a propósito: la lógica vive en el modelo."""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.shortcuts import render

from martina_bescos_app.users.permisos import es_profesor
from repertorio.consulta import interpretar_consulta
from repertorio.models import Cancion, Sincronizacion

# Qué parámetro de la URL alimenta qué filtro de `Cancion.buscar()`.
PARAMETROS = {
    "decada": "decada",
    "acordes": "num_acordes",
    "instrumento": "instrumento",
    "nivel": "nivel",
    "progresion": "progresion",
    "tonalidad": "tonalidad",
    "modo": "modo",
    "idioma": "idioma",
    "curso": "curso",
    "origen": "origen",
}


def _valores(request, nombre):
    """Los valores de un parámetro, admitiendo `?x=a&x=b` y `?x=a,b`.

    HTMX puede mandar el mismo valor dos veces cuando el formulario entero va en
    `hx-include`, así que se deduplica conservando el orden.
    """
    crudos = []
    for bruto in request.GET.getlist(nombre):
        crudos.extend(parte.strip() for parte in bruto.split(","))
    return list(dict.fromkeys(v for v in crudos if v))


def _filtros_desde_peticion(request):
    """Los filtros efectivos: los de las píldoras más los de la caja de texto."""
    filtros = {}
    for parametro, clave in PARAMETROS.items():
        valores = _valores(request, parametro)
        if not valores:
            continue
        filtros[clave] = [int(v) for v in valores] if clave in ("decada", "num_acordes") and all(
            v.isdigit() for v in valores
        ) else valores

    if request.GET.get("favorito"):
        filtros["favorito"] = True

    texto = (request.GET.get("q") or "").strip()
    interpretados, chips, resto = interpretar_consulta(texto)

    # Lo que ya está marcado a mano manda: la caja solo añade dimensiones que
    # no estuvieran puestas, para que escribir no borre lo que has clicado.
    for clave, valor in interpretados.items():
        filtros.setdefault(clave, valor)

    if resto:
        filtros["texto"] = resto

    return filtros, chips, texto, resto


@login_required
@user_passes_test(es_profesor, login_url="/accounts/login/", redirect_field_name=None)
def catalogo(request):
    filtros, chips, texto, resto = _filtros_desde_peticion(request)

    canciones = (
        Cancion.buscar(**filtros)
        .prefetch_related("artistas", "generos", "idiomas", "versiones")
        .order_by("titulo")
    )
    paginador = Paginator(canciones, 24)
    pagina = paginador.get_page(request.GET.get("page"))

    contexto = {
        "pagina": pagina,
        "total": paginador.count,
        "facetas": Cancion.facetas(filtros),
        "chips": chips,
        "texto": texto,
        "resto": resto,
        "hay_filtros": bool(filtros),
        "sincronizacion": Sincronizacion.ultima(),
    }

    plantilla = (
        "repertorio/partials/panel.html"
        if request.headers.get("HX-Request")
        else "repertorio/catalogo.html"
    )
    return render(request, plantilla, contexto)
