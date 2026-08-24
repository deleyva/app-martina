"""Escritura de etiquetas en las páginas, para el API.

Desde C37b las páginas tienen un solo vocabulario: `faceted_tags` (taggit,
`faceta:valor`). El API recibe NOMBRES, no ids: los ids eran de `MusicTag`, que
ya no existe, y un nombre facetado se lee y se escribe a mano sin consultar
nada. `PublishIES` publica por aquí.
"""

from django.utils.text import slugify

from my_library import facets


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


def facetas_desconocidas(nombres):
    """Los nombres con pinta de faceta cuya faceta no existe.

    `estilo:jazz` pasa; `caracter:melancolico` no, porque `caracter` no está en
    `facets.FACETAS`. Sin esta comprobación la etiqueta se crearía igual pero
    nacería muerta: la biblioteca la trataría como plana y no agruparía ni
    filtraría. Un nombre SIN dos puntos (`vitalinux`, `3/4`) es válido y pasa.
    """
    malos = []
    for nombre in nombres:
        if facets.SEPARADOR not in nombre:
            continue
        if facets.parse(nombre)[0] is None:
            malos.append(nombre)
    return malos


def aplicar_etiquetas(pagina, nombres):
    """Pone en la página las etiquetas facetadas indicadas, por nombre.

    Crea las que no existan. No persiste: `set()` sobre modelcluster deja el
    cambio en memoria y quien llama guarda después con `save_revision()`, que es
    lo que hace el API.
    """
    from taggit.models import Tag

    etiquetas = []
    vistos = set()
    for nombre in nombres:
        nombre = nombre.strip()
        if not nombre or nombre.lower() in vistos:
            continue
        vistos.add(nombre.lower())
        tag, _ = Tag.objects.get_or_create(
            name=nombre, defaults={"slug": _slug_para(nombre)}
        )
        etiquetas.append(tag)

    pagina.faceted_tags.set(etiquetas)
