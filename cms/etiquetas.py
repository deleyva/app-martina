"""Traducción del vocabulario plano al facetado, para los escritores del API.

Mientras dure la fase 8 conviven dos vocabularios en las páginas: `tags`
(`cms.MusicTag`, plano, el que reciben los endpoints como `tag_ids`) y
`faceted_tags` (taggit, `faceta:valor`, el que lee la sesión de estudio desde
C36). Todo lo que escriba en uno tiene que escribir en el otro, o la duplicación
vuelve a separarse en cuanto se publique un artículo.

El caso real que esto cubre: la skill PublishIES del principal publica por
`POST /api/cms/blog-pages` mandando `tag_ids`. Sin esto, cada artículo nuevo
nacería con etiquetas planas invisibles para la sesión.

Desaparece con C37b, cuando el API pase a hablar en nombres facetados.
"""

from pathlib import Path

from django.utils.text import slugify

MAPA = (
    Path(__file__).resolve().parent.parent
    / "my_library"
    / "migracion"
    / "mapa_musictags.txt"
)
BORRAR = "__BORRAR__"


def _leer_mapa():
    mapa = {}
    for linea in MAPA.read_text().splitlines():
        linea = linea.split("#")[0].strip()
        if "->" not in linea:
            continue
        origen, _, destino = linea.partition("->")
        origen, destino = origen.strip(), destino.strip()
        if origen and destino:
            mapa[origen.lower()] = destino
    return mapa


def _slug_para(nombre):
    """Los dos puntos van a guion antes de slugificar, o `estilo:jazz` daría
    `estilojazz`. Misma trampa que documenta `migrar_etiquetas.slug_para`."""
    from taggit.models import Tag

    base = slugify(nombre.replace(":", "-")) or "etiqueta"
    slug, n = base, 2
    while Tag.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def facetadas_para(musictags):
    """Las etiquetas de taggit equivalentes a una lista de `MusicTag`.

    Las que el mapa manda a `__BORRAR__` se caen, que es la decisión que tomó
    el principal al revisarlo. Un nombre que el mapa no conozca se deja pasar
    tal cual: es una etiqueta nueva creada en el admin después de cerrar el
    mapa, y perderla en silencio sería peor que dejarla sin faceta.
    """
    from taggit.models import Tag

    mapa = _leer_mapa()
    nombres = []
    for etiqueta in musictags:
        destino = mapa.get(etiqueta.name.lower(), etiqueta.name)
        if destino == BORRAR:
            continue
        if destino not in nombres:  # el mapa fusiona: dos orígenes, un destino
            nombres.append(destino)

    resultado = []
    for nombre in nombres:
        tag, _ = Tag.objects.get_or_create(
            name=nombre, defaults={"slug": _slug_para(nombre)}
        )
        resultado.append(tag)
    return resultado


def aplicar_etiquetas(pagina, musictags):
    """Escribe en los DOS vocabularios. Un solo sitio al que llamar."""
    pagina.tags.set(musictags)
    pagina.faceted_tags.set(facetadas_para(musictags))
