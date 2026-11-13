"""El ancla de una pregunta: de qué elemento del material sale (fase 107).

Lo que hay aquí es lo que comparten el API, el formulario y el banco: listar
el material de una página con un índice estable dentro de ella, anclar por ese
índice y decir en una línea a qué está anclada una pregunta.
"""

from django.contrib.contenttypes.models import ContentType
from wagtail.models import Page

from clases.libros_de_grupo import describir
from my_library.libros import material_de, material_del_libro


def _objetos_de(pagina):
    """Los medios de una página en su orden. Vale para capítulo y para libro."""
    especifica = pagina.specific
    if callable(getattr(especifica, "paginas_referenciadas", None)):
        return [objeto for _, objeto in material_del_libro(especifica)]
    return list(material_de(especifica))


def material_listado(pagina):
    """[{indice, tipo, id, titulo, clase}] del material de la página.

    `indice` empieza en 0 y es la posición de hoy: sirve para anclar, no para
    guardarlo. Lo que se guarda es `(tipo, id)`, que no cambia si se reordena.
    """
    salida = []
    for indice, objeto in enumerate(_objetos_de(pagina)):
        icono, titulo, clase = describir(objeto)
        tipo = ContentType.objects.get_for_model(objeto.__class__)
        salida.append(
            {
                "indice": indice,
                "tipo": f"{tipo.app_label}.{tipo.model}",
                "tipo_id": tipo.pk,
                "id": objeto.pk,
                "titulo": f"{icono} {titulo}",
                "clase": clase,
            }
        )
    return salida


def anclar(pregunta, pagina, tipo_id, objeto_id, guardar=True):
    """Ancla la pregunta a un medio que ESTÉ en el material de la página."""
    claves = {(m["tipo_id"], m["id"]) for m in material_listado(pagina)}
    if (tipo_id, objeto_id) not in claves:
        raise ValueError("Ese elemento no está en el material de la página.")
    pregunta.ancla_tipo_id = tipo_id
    pregunta.ancla_id = objeto_id
    pregunta.ancla_pagina = pagina
    if guardar:
        pregunta.save()
    return pregunta


def desanclar(pregunta, guardar=True):
    pregunta.ancla_tipo = None
    pregunta.ancla_id = None
    pregunta.ancla_pagina = None
    if guardar:
        pregunta.save()
    return pregunta


def descripcion(pregunta):
    """«Título del elemento · Página», o None sin ancla o con el objeto borrado."""
    if not pregunta.anclada:
        return None
    objeto = pregunta.ancla
    pagina = pregunta.ancla_pagina
    if objeto is None:
        return None
    _, titulo, clase = describir(objeto)
    return f"{titulo} ({clase})" + (f" · {pagina.title}" if pagina else "")


def paginas_candidatas(pregunta=None):
    """Páginas entre las que elegir ancla en el formulario: las que ya tienen
    preguntas ancladas y los libros y capítulos de Teoría de los grupos."""
    from clases.models import GroupBook
    from my_library.libros import capitulos_de

    from .models import Pregunta

    ids = set(Pregunta.objects.exclude(ancla_pagina=None).values_list("ancla_pagina_id", flat=True))
    for group_book in GroupBook.objects.filter(seccion="teoria").select_related("libro"):
        libro = group_book.libro.specific
        ids.add(libro.pk)
        try:
            ids.update(c.pk for c in capitulos_de(libro) if isinstance(c, Page))
        except Exception:
            continue
    if pregunta is not None and pregunta.ancla_pagina_id:
        ids.add(pregunta.ancla_pagina_id)
    return list(Page.objects.filter(pk__in=ids).order_by("title"))
