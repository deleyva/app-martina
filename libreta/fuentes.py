"""De dónde salen los elementos: las plantillas del CMS y el índice de recursos.

Las plantillas son la página `plantillas-para-escribir`, la misma que abre el
visor de clase; se leen con `material_de`, el recorrido que ya usan los
libros, así que lo que se suba a esa página en el CMS aparece aquí sin tocar
código. Solo valen PDF e imágenes: un audio no se fotocopia.
"""

from __future__ import annotations

from clases.views_libros import SLUG_PLANTILLAS
from my_library.libros import material_de

MINIMO_PARA_BUSCAR = 2  # letras; con una sola, medio índice


def _fotocopiable(objeto) -> bool:
    nombre = objeto.__class__.__name__.lower()
    if nombre == "image":
        return True
    return nombre == "document" and objeto.file.name.lower().endswith(".pdf")


def _describir(objeto) -> dict:
    """Lo que la plantilla necesita para pintar el botón de añadir."""
    tipo = "imagen" if objeto.__class__.__name__.lower() == "image" else "documento"
    return {
        "tipo": tipo,
        "pk": objeto.pk,
        "titulo": getattr(objeto, "title", "") or str(objeto),
    }


def _medios(pagina) -> list[dict]:
    return [_describir(m) for m in material_de(pagina.specific) if _fotocopiable(m)]


def plantillas() -> list[dict]:
    from wagtail.models import Page

    pagina = Page.objects.filter(slug=SLUG_PLANTILLAS).live().first()
    return _medios(pagina) if pagina else []


def buscar(texto: str, limite: int = 15) -> list[tuple]:
    """[(página, [medios])] del índice de recursos cuyo título contiene `texto`."""
    from wagtail.models import Page

    from musica.models import MusicLibraryIndexPage
    from musica.models import q_texto

    texto = (texto or "").strip()
    if len(texto) < MINIMO_PARA_BUSCAR:
        return []
    indice = MusicLibraryIndexPage.objects.live().first()
    if indice is None:
        return []
    paginas = (
        Page.objects.live()
        .descendant_of(indice)
        .filter(q_texto("title", texto))
        .order_by("title")[:limite]
    )
    salida = []
    for pagina in paginas:
        medios = _medios(pagina)
        if medios:
            salida.append((pagina, medios))
    return salida


def medio(tipo: str, pk) -> object | None:
    """El `Document` o `Image` de Wagtail que se quiere añadir, o `None`."""
    from wagtail.documents import get_document_model
    from wagtail.images import get_image_model

    modelo = {"documento": get_document_model(), "imagen": get_image_model()}.get(tipo)
    if modelo is None:
        return None
    objeto = modelo.objects.filter(pk=pk).first()
    return objeto if objeto is not None and _fotocopiable(objeto) else None
