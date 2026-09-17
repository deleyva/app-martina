"""API de recortes: trocear un PDF sin pasar por la pantalla.

**Para que.** La pantalla de recorte resuelve el caso de un metodo con el que se
trabaja delante. Pero cuando un libro tiene cuarenta ejercicios y ya se sabe en
que paginas caen, dibujarlos uno a uno es trabajo mecanico. Con `lote` se monta
el libro entero en una llamada.

Mismo patron que `cms` y `content_hub`: router de Django Ninja con
`DatabaseApiKey` y `django_auth`, cabecera `X-API-Key`.

**La validacion NO se repite aqui.** Todo pasa por `Recorte.full_clean()`, que
es el mismo sitio por el que pasa el formulario de la pantalla. Duplicar las
reglas en el esquema garantiza que un dia digan cosas distintas.
"""

from typing import List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.security import django_auth
from wagtail.documents.models import Document

from api_keys.auth import DatabaseApiKey
from martina_bescos_app.users.permisos import es_profesor
from musica.models import DocumentoRestringido, LibroDeEstudioPage, Recorte

router = Router(tags=["Recortes"], auth=[DatabaseApiKey(), django_auth])


class RecorteIn(Schema):
    """Un recorte. Solo `nombre` y `pagina_desde` son obligatorios."""

    nombre: str
    pagina_desde: int = 1
    pagina_hasta: Optional[int] = None
    pagina_offset_impresa: Optional[int] = None
    rect_x0: Optional[float] = None
    rect_y0: Optional[float] = None
    rect_x1: Optional[float] = None
    rect_y1: Optional[float] = None
    tags: List[str] = []


class LoteIn(Schema):
    documento_id: int
    recortes: List[RecorteIn]
    # A que libro se anaden, en el orden en que vienen. Sin esto se crean
    # sueltos, que es lo util cuando todavia no se sabe como se agrupan.
    libro_id: Optional[int] = None


class RecorteOut(Schema):
    id: int
    nombre: str
    documento_id: int
    pagina_desde: int
    pagina_hasta: Optional[int]
    etiqueta_de_paginas: str
    tiene_rect: bool
    se_sirve_cortado: bool


class LoteOut(Schema):
    creados: List[RecorteOut]
    libro_id: Optional[int] = None
    total_capitulos: Optional[int] = None


def _exigir_profesor(request):
    """Una clave de API vale lo que vale su duena.

    `DatabaseApiKey` autentica COMO EL USUARIO que creo la clave, sin ambito ni
    permisos propios. Sin esta comprobacion, la clave de un alumno crearia
    contenido publicado; y en `api_keys` cualquiera con sesion puede crearse una.
    """
    if not es_profesor(request.user):
        raise HttpError(403, "Solo el profesorado puede crear recortes.")


def _documento_pdf(documento_id: int) -> Document:
    documento = Document.objects.filter(pk=documento_id).first()
    if documento is None:
        raise HttpError(404, f"No hay ningún documento con id {documento_id}.")
    nombre = documento.file.name.lower() if documento.file else ""
    if not nombre.endswith(".pdf"):
        raise HttpError(400, "Solo se pueden recortar PDF.")
    return documento


def _construir(documento: Document, datos: RecorteIn) -> Recorte:
    recorte = Recorte(
        documento=documento,
        nombre=datos.nombre.strip()[:200],
        pagina_desde=datos.pagina_desde,
        pagina_hasta=datos.pagina_hasta,
        pagina_offset_impresa=datos.pagina_offset_impresa,
        rect_x0=datos.rect_x0,
        rect_y0=datos.rect_y0,
        rect_x1=datos.rect_x1,
        rect_y1=datos.rect_y1,
    )
    if not recorte.nombre:
        raise HttpError(400, "El recorte necesita un nombre.")
    try:
        recorte.full_clean(exclude=["documento"])
    except ValidationError as e:
        detalle = "; ".join(
            f"{campo}: {' '.join(mensajes)}"
            for campo, mensajes in e.message_dict.items()
        )
        raise HttpError(400, f"«{recorte.nombre}» no es válido. {detalle}")
    return recorte


def _salida(recorte: Recorte) -> RecorteOut:
    return RecorteOut(
        id=recorte.pk,
        nombre=recorte.nombre,
        documento_id=recorte.documento_id,
        pagina_desde=recorte.pagina_desde,
        pagina_hasta=recorte.pagina_hasta,
        etiqueta_de_paginas=recorte.etiqueta_de_paginas,
        tiene_rect=recorte.tiene_rect,
        se_sirve_cortado=recorte.se_sirve_cortado,
    )


@router.post("/lote", response=LoteOut)
def crear_lote(request, payload: LoteIn):
    """Crea varios recortes de un PDF y, si se pide, los añade a un libro.

    **Todo o nada.** Va en una transacción a propósito: un lote a medias deja un
    libro con la mitad de los capítulos y sin forma de saber por dónde iba. Si
    uno falla la validación, no se crea ninguno y la respuesta dice cuál.

    El orden de la lista es el orden de los capítulos, igual que en
    `/api/cms/study-books/{id}/chapters`.
    """
    _exigir_profesor(request)
    documento = _documento_pdf(payload.documento_id)

    if not payload.recortes:
        raise HttpError(400, "`recortes` está vacío: no hay nada que crear.")

    libro = None
    if payload.libro_id is not None:
        libro = LibroDeEstudioPage.objects.filter(pk=payload.libro_id).first()
        if libro is None:
            raise HttpError(404, f"No hay ningún libro con id {payload.libro_id}.")

    construidos = [_construir(documento, datos) for datos in payload.recortes]

    with transaction.atomic():
        creados = []
        for recorte, datos in zip(construidos, payload.recortes):
            recorte.save()
            if datos.tags:
                recorte.tags.add(*datos.tags)
            creados.append(recorte)
            if libro is not None:
                libro.capitulos.append(("recorte", recorte))
        if libro is not None:
            libro.save()
            libro.save_revision().publish()
            libro.refresh_from_db()

    return LoteOut(
        creados=[_salida(r) for r in creados],
        libro_id=libro.pk if libro else None,
        total_capitulos=len(libro.capitulos) if libro else None,
    )


@router.get("/documento/{documento_id}", response=List[RecorteOut])
def listar_del_documento(request, documento_id: int):
    """Los recortes que ya tiene un PDF, por página.

    Es lo que evita duplicar al reintentar: el cliente mira qué hay antes de
    mandar el lote.
    """
    _exigir_profesor(request)
    documento = _documento_pdf(documento_id)
    return [
        _salida(r)
        for r in Recorte.objects.filter(documento=documento).order_by(
            "pagina_desde", "nombre"
        )
    ]


class RestriccionIn(Schema):
    restringido: bool = True
    motivo: str = ""


class RestriccionOut(Schema):
    documento_id: int
    restringido: bool
    motivo: str


@router.post("/documento/{documento_id}/restriccion", response=RestriccionOut)
def marcar_restriccion(request, documento_id: int, payload: RestriccionIn):
    """Marca un PDF como servible solo por sus recortes, o lo desmarca.

    Marcarlo hace dos cosas a la vez: su URL de documento deja de entregar nada,
    y sus recortes pasan a servirse como PDF cortados al rango. Desmarcarlo
    vuelve a servir el documento entero.
    """
    _exigir_profesor(request)
    documento = _documento_pdf(documento_id)

    if payload.restringido:
        restriccion, _ = DocumentoRestringido.objects.update_or_create(
            documento=documento,
            defaults={"solo_por_recorte": True, "motivo": payload.motivo[:200]},
        )
        return RestriccionOut(
            documento_id=documento.pk, restringido=True, motivo=restriccion.motivo
        )

    DocumentoRestringido.objects.filter(documento=documento).delete()
    return RestriccionOut(documento_id=documento.pk, restringido=False, motivo="")


class LibroIn(Schema):
    titulo: str
    slug: Optional[str] = None
    intro: str = ""
    # Donde cuelga. Por defecto, el indice de recursos musicales: es el sitio
    # donde ya viven los libros, y adivinarlo evita pedir un id que el cliente
    # tendria que averiguar antes.
    parent_id: Optional[int] = None


class LibroOut(Schema):
    id: int
    title: str
    url: str
    edit_url: str


@router.post("/libro", response=LibroOut)
def crear_libro(request, payload: LibroIn):
    """Crea un libro de estudio vacío, listo para recibir recortes.

    Existe aquí y no en `cms` porque completa este flujo: subir el PDF, crear el
    libro, mandar el lote. Sin él hay que salir al admin en mitad del camino, y
    montar un método de cuarenta piezas por API deja de tener sentido.
    """
    from django.utils.text import slugify
    from musica.models import MusicLibraryIndexPage

    _exigir_profesor(request)

    if payload.parent_id is not None:
        from wagtail.models import Page as WagtailPage

        padre = WagtailPage.objects.filter(pk=payload.parent_id).first()
        if padre is None:
            raise HttpError(404, f"No hay ninguna página con id {payload.parent_id}.")
    else:
        padre = MusicLibraryIndexPage.objects.first()
        if padre is None:
            raise HttpError(
                400,
                "No hay índice de recursos musicales: indica `parent_id`.",
            )

    slug = (payload.slug or slugify(payload.titulo))[:255]
    if padre.get_children().filter(slug=slug).exists():
        raise HttpError(400, f"Ya hay una página con el slug «{slug}» ahí.")

    libro = LibroDeEstudioPage(
        title=payload.titulo[:255], slug=slug, intro=payload.intro, capitulos=[]
    )
    padre.add_child(instance=libro)
    libro.save_revision().publish()
    libro.refresh_from_db()

    return LibroOut(
        id=libro.pk,
        title=libro.title,
        url=libro.url or "",
        edit_url=f"/cms/pages/{libro.pk}/edit/",
    )
