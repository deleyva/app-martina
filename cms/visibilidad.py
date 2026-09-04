"""Visibilidad de páginas: `is_protected` (pide login) e `is_private` (solo el dueño).

Vivía dentro de `cms/models.py` cuando blog y música eran la misma app. Al partir
`cms` en `blogs` y `musica` (fase 25) hay que compartirlo, porque los dos lados
tienen páginas con estos dos campos y la herencia va por el árbol, que es único y
cruza las dos apps.

El cambio de fondo respecto a la versión anterior: `TIPOS_CON_VISIBILIDAD` era una
tupla escrita a mano, y el comentario que la acompañaba avisaba de que añadir un
tipo obligaba a acordarse de tres sitios. Con los modelos repartidos en dos apps
esa tupla sería directamente una trampa: un modelo nuevo en `musica` no se vería
desde `cms`. Ahora se descubre: cualquier `Page` que declare los dos campos entra
sola. El registro se cachea porque el árbol de modelos no cambia en caliente.
"""

from functools import lru_cache

from django.db import models
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings


def _login_redirect(request):
    """Manda al login conservando el `?next=` para volver donde estabas."""
    login_url = reverse(settings.LOGIN_URL)
    return redirect(f"{login_url}?next={request.path}")


@lru_cache(maxsize=1)
def tipos_con_visibilidad():
    """Todos los modelos `Page` que declaran `is_protected` e `is_private`.

    Se descubre en vez de listarse: con los modelos repartidos entre `blogs` y
    `musica`, una lista a mano se queda corta en cuanto alguien añade un tipo en
    la app en la que no está mirando.
    """
    from wagtail.models import Page

    encontrados = []
    for modelo in Page.__subclasses__() + _subclases_profundas(Page):
        campos = {f.name for f in modelo._meta.get_fields() if hasattr(f, "name")}
        if {"is_protected", "is_private"} <= campos:
            encontrados.append(modelo)
    return tuple(dict.fromkeys(encontrados))


def _subclases_profundas(clase):
    """Subclases a cualquier profundidad, no solo las hijas directas."""
    salida = []
    for hija in clase.__subclasses__():
        salida.append(hija)
        salida.extend(_subclases_profundas(hija))
    return salida


def ancestro_con(ancestors, campo):
    """El primer ancestro con ese campo de visibilidad puesto, o None.

    Se consulta por tipo porque el campo vive en la tabla concreta de cada
    modelo, no en `Page`.
    """
    for modelo in tipos_con_visibilidad():
        clave = f"{modelo._meta.model_name}__{campo}"
        encontrado = ancestors.type(modelo).filter(**{clave: True}).first()
        if encontrado is not None:
            return encontrado
    return None


def check_page_visibility(page, request):
    """None si la página es accesible; si no, la respuesta que la deniega.

    Mira la página y sus ancestros, porque proteger un departamento protege lo
    que cuelga de él.
    """
    tipos = tipos_con_visibilidad()
    es_tipo_con_visibilidad = isinstance(page, tipos)
    ancestors = page.get_ancestors()

    # Atajo barato: ni ella ni ningún ancestro llevan campos de visibilidad.
    if not es_tipo_con_visibilidad:
        if not any(ancestors.type(modelo).exists() for modelo in tipos):
            return None

    protected = False
    private_owner = None

    # Una página privada SIN owner no puede quedar pública. La comprobación de
    # abajo se activa con `private_owner is not None`, así que un owner nulo
    # saltaba el bloqueo entero y la página se servía a cualquiera con la URL,
    # aunque los listados sí la escondieran. Media privacidad se lee como
    # privacidad. Con `sin_dueno` queda visible solo para superusuarios
    # (2026-08-29: lo destaparon 31 páginas creadas por API, que nacen sin owner).
    sin_dueno = False

    if es_tipo_con_visibilidad:
        if page.is_private:
            private_owner = page.owner
            sin_dueno = page.owner is None
        if page.is_protected:
            protected = True

    private_ancestor = ancestro_con(ancestors, "is_private")
    if private_ancestor:
        private_owner = private_ancestor.owner
        sin_dueno = private_ancestor.owner is None

    if not protected:
        protected = ancestro_con(ancestors, "is_protected") is not None

    # Privada manda sobre protegida.
    if private_owner is not None or sin_dueno:
        if not request.user.is_authenticated:
            return _login_redirect(request)
        if request.user.is_superuser:
            return None
        if sin_dueno or request.user != private_owner:
            return HttpResponseForbidden("No tienes permiso para ver esta página.")
        return None

    if protected and not request.user.is_authenticated:
        return _login_redirect(request)

    return None


def filter_visible_pages(queryset, request):
    """Quita de un listado lo que el usuario no debe ver.

    Solo mira los campos de la propia página. La herencia por ancestros la
    aplica `check_page_visibility` al servir.
    """
    if request.user.is_superuser:
        return queryset

    if request.user.is_authenticated:
        # `owner=request.user` no casa cuando owner es NULL, así que una privada
        # sin dueño ya queda excluida aquí. Se deja explícito para que no se
        # pierda si alguien reescribe la condición.
        return queryset.exclude(
            models.Q(is_private=True)
            & (models.Q(owner__isnull=True) | ~models.Q(owner=request.user))
        )

    return queryset.exclude(
        models.Q(is_protected=True) | models.Q(is_private=True)
    )
