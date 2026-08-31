from datetime import date
from typing import List, Optional

from django.db import transaction
from django.utils import timezone
from ninja import Router, Schema, File, Form
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja.security import django_auth
from wagtail.documents import get_document_model
from wagtail.images import get_image_model
from wagtail.models import Collection, Page as WagtailPage

from api_keys.auth import DatabaseApiKey
from .models import (
    BlogIndexPage,
    BlogPage,
    MusicCategory,
    MusicLibraryIndexPage,
    TestPage,
)
from my_library import facets

from .etiquetas import aplicar_etiquetas, facetas_desconocidas
from .services import AIMetadataExtractor, ContentPublisher


router = Router(tags=["CMS Tests"], auth=[DatabaseApiKey(), django_auth])


def _validar_etiquetas(payload):
    """`tag_ids` se retiró con `MusicTag` (C37b).

    Falla alto en vez de ignorarlo: un cliente viejo que siga mandando ids
    numéricos publicaría artículos sin etiquetas y nadie se enteraría hasta
    buscarlos meses después.
    """
    if getattr(payload, "tag_ids", None):
        raise HttpError(
            400,
            "`tag_ids` ya no existe: MusicTag se retiró. Manda `tags` con "
            'nombres facetados, por ejemplo ["estilo:jazz", "instrumento:guitarra"].',
        )

    desconocidas = facetas_desconocidas(getattr(payload, "tags", None) or [])
    if desconocidas:
        raise HttpError(
            400,
            f"Faceta desconocida en {desconocidas}. La etiqueta se crearía pero "
            "nacería muerta: la biblioteca la trataría como plana y no agruparía "
            f"ni filtraría. Facetas válidas: {', '.join(facets.FACETAS)}.",
        )
DocumentModel = get_document_model()
ImageModel = get_image_model()


class AnswerOptionIn(Schema):
    text: str
    is_correct: bool = False
    image_id: Optional[int] = None


class QuestionIn(Schema):
    prompt: str
    description: Optional[str] = None
    explanation: Optional[str] = None
    illustration_image_id: Optional[int] = None
    options: List[AnswerOptionIn]


class TestPageIn(Schema):
    title: str
    intro: Optional[str] = None
    date: Optional[date] = None
    featured_image_id: Optional[int] = None
    parent_page_id: Optional[int] = None
    category_ids: List[int] = []
    tags: List[str] = []
    # Retirado con `MusicTag` (C37b). Se mantiene en el esquema para poder
    # rechazarlo con un 400 explícito: un cliente viejo que lo mandara perdería
    # sus etiquetas en silencio, que es peor que un error.
    tag_ids: List[int] = []
    questions: List[QuestionIn]


class TestPageOut(Schema):
    id: int
    title: str
    url: str
    question_count: int


def _get_image(image_id: Optional[int]):
    if image_id is None:
        return None
    try:
        return ImageModel.objects.get(id=image_id)
    except ImageModel.DoesNotExist as exc:
        raise HttpError(400, f"La imagen con ID {image_id} no existe.") from exc


def _get_parent_page(parent_page_id: Optional[int]) -> MusicLibraryIndexPage:
    if parent_page_id is not None:
        try:
            return MusicLibraryIndexPage.objects.get(id=parent_page_id)
        except MusicLibraryIndexPage.DoesNotExist as exc:
            raise HttpError(400, "La página padre indicada no existe.") from exc
    parent = MusicLibraryIndexPage.objects.first()
    if not parent:
        raise HttpError(
            400, "No existe ninguna MusicLibraryIndexPage para anexar el test."
        )
    return parent


def _build_questions_payload(questions: List[QuestionIn]):
    stream_value = []
    for question in questions:
        if len(question.options) != 4:
            raise HttpError(400, "Cada pregunta debe tener exactamente 4 opciones.")
        correct_count = sum(1 for option in question.options if option.is_correct)
        if correct_count != 1:
            raise HttpError(
                400,
                "Cada pregunta debe tener exactamente una opción marcada como correcta.",
            )
        illustration = _get_image(question.illustration_image_id)
        option_values = []
        for option in question.options:
            option_values.append(
                {
                    "text": option.text,
                    "is_correct": option.is_correct,
                    "image": _get_image(option.image_id),
                }
            )
        stream_value.append(
            (
                "question",
                {
                    "prompt": question.prompt,
                    "description": question.description,
                    "illustration": illustration,
                    "options": option_values,
                    "explanation": question.explanation,
                },
            )
        )
    return stream_value


@router.post("/tests", response=TestPageOut)
def create_test_page(request, payload: TestPageIn):
    if not payload.questions:
        raise HttpError(400, "Debes enviar al menos una pregunta.")

    parent_page = _get_parent_page(payload.parent_page_id)
    featured_image = _get_image(payload.featured_image_id)
    questions_value = _build_questions_payload(payload.questions)

    with transaction.atomic():
        page = TestPage(
            title=payload.title,
            intro=payload.intro or "",
            date=payload.date or timezone.now().date(),
        )
        if featured_image:
            page.featured_image = featured_image
        page.questions = questions_value
        parent_page.add_child(instance=page)

        if payload.category_ids:
            categories = list(
                MusicCategory.objects.filter(id__in=payload.category_ids).distinct()
            )
            if len(categories) != len(set(payload.category_ids)):
                raise HttpError(400, "Alguna categoría proporcionada no existe.")
            page.categories.set(categories)
        _validar_etiquetas(payload)
        if payload.tags:
            aplicar_etiquetas(page, payload.tags)

        page.save_revision().publish()

    return TestPageOut(
        id=page.id,
        title=page.title,
        url=page.get_url(request),
        question_count=len(payload.questions),
    )


# AI-Powered Publishing Endpoint
# ------------------------------------------------------------------------------


class AIPublishOut(Schema):
    """Response schema for AI-powered publishing"""

    success: bool
    score_page_id: int
    title: str
    edit_url: str
    preview_url: str
    message: str
    created_items: dict


@router.post("/ai-publish", response=AIPublishOut)
def ai_publish_content(
    request,
    description: str = Form(..., description="Descripción en lenguaje natural del contenido"),
    page_type: str = Form("scorepage", description="Tipo de página: 'scorepage', 'dictadopage' o 'blogpage'"),
    publish_immediately: bool = Form(False, description="Si True, publicar inmediatamente; si False, guardar como borrador"),
    parent_page_id: Optional[int] = Form(None, description="ID de la página padre (opcional)"),
    pdf_files: List[UploadedFile] = File(None, description="Archivos PDF de partituras"),
    audio_files: List[UploadedFile] = File(None, description="Archivos de audio (MP3, WAV, etc.)"),
    image_files: List[UploadedFile] = File(None, description="Archivos de imagen"),
    midi_files: List[UploadedFile] = File(None, description="Archivos MIDI"),
):
    """
    Crear ScorePage o DictadoPage usando IA para procesar descripción en lenguaje natural.

    Este endpoint permite subir archivos musicales (PDFs, audios, imágenes, MIDI)
    junto con una descripción en lenguaje natural. La IA extrae automáticamente
    metadata estructurada (título, compositor, dificultad, etc.) y crea la página
    correspondiente en Wagtail.
    
    Para ScorePage: PDFs, audios e imágenes se agregan como bloques de contenido.
    Para DictadoPage: Audios se muestran con WaveSurfer.js, PDFs e imágenes como respuestas colapsables.

    Proceso:
    1. Validar archivos y descripción
    2. Extraer metadata con IA (Google Gemini)
    3. Crear ScorePage con ContentPublisher
    4. Retornar URLs de edición

    Args:
        request: Request object
        description: Descripción en lenguaje natural del contenido
        publish_immediately: Si True, publicar; si False, guardar como borrador
        parent_page_id: ID de la página padre (opcional)
        pdf_files: Lista de archivos PDF
        audio_files: Lista de archivos de audio
        image_files: Lista de imágenes
        midi_files: Lista de archivos MIDI

    Returns:
        AIPublishOut con información de la página creada

    Raises:
        HttpError 400: Si faltan datos requeridos o son inválidos
        HttpError 500: Si falla la creación de la página
    """
    # Validaciones básicas
    if not description or not description.strip():
        raise HttpError(400, "Debes proporcionar una descripción.")

    # Convertir None a listas vacías
    pdf_files = pdf_files or []
    audio_files = audio_files or []
    image_files = image_files or []
    midi_files = midi_files or []

    if not any([pdf_files, audio_files, image_files, midi_files]):
        raise HttpError(400, "Debes subir al menos un archivo.")

    # Preparar nombres de archivos para la IA
    file_names = []
    if pdf_files:
        file_names.extend([f"PDF: {f.name}" for f in pdf_files])
    if audio_files:
        file_names.extend([f"Audio: {f.name}" for f in audio_files])
    if image_files:
        file_names.extend([f"Imagen: {f.name}" for f in image_files])
    if midi_files:
        file_names.extend([f"MIDI: {f.name}" for f in midi_files])

    # Get parent page si se especificó
    parent_page = None
    if parent_page_id:
        try:
            parent_page = MusicLibraryIndexPage.objects.get(id=parent_page_id)
        except MusicLibraryIndexPage.DoesNotExist as exc:
            raise HttpError(400, "La página padre indicada no existe.") from exc

    # Extraer metadata con IA
    try:
        extractor = AIMetadataExtractor()
        metadata = extractor.extract_metadata(description, file_names)
        
        # Log the extracted metadata for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"AI metadata extraction result: title='{metadata.get('title')}', "
            f"composer='{metadata.get('composer')}', "
            f"categories={metadata.get('categories')}, "
            f"tags={metadata.get('tags')}"
        )
        
        # Check if we got fallback values (indicating API failure)
        if metadata.get('title') == 'Sin título' or not metadata.get('composer'):
            logger.warning(
                "AI metadata extraction returned default values - possible API failure. "
                f"Title: '{metadata.get('title')}', Composer: '{metadata.get('composer')}'"
            )
            
    except ValueError as e:
        raise HttpError(400, f"Error en la descripción: {str(e)}")
    except Exception as e:
        # More specific error message for AI failures
        logger.error(f"AI metadata extraction failed: {e}", exc_info=True)
        raise HttpError(
            500, 
            f"Error al procesar con IA: {str(e)}. Por favor, verifica la configuración de GEMINI_API_KEY."
        )

    # Crear ScorePage o DictadoPage con transaction
    try:
        with transaction.atomic():
            publisher = ContentPublisher(user=request.auth)  # auth is the User from DatabaseApiKey
            
            if page_type == 'dictadopage':
                # Create DictadoPage
                page = publisher.create_dictadopage_from_ai(
                    metadata=metadata,
                    pdf_files=pdf_files,
                    audio_files=audio_files,
                    image_files=image_files,
                    midi_files=midi_files,
                    publish=publish_immediately,
                    parent_page=parent_page,
                )
            elif page_type == 'blogpage':
                # Create BlogPage
                page = publisher.create_blogpage_from_ai(
                    metadata=metadata,
                    pdf_files=pdf_files,
                    audio_files=audio_files,
                    image_files=image_files,
                    midi_files=midi_files,
                    publish=publish_immediately,
                    parent_page=parent_page,
                )
            else:
                # Create ScorePage (default)
                page = publisher.create_scorepage_from_ai(
                    metadata=metadata,
                    pdf_files=pdf_files,
                    audio_files=audio_files,
                    image_files=image_files,
                    midi_files=midi_files,
                    publish=publish_immediately,
                    parent_page=parent_page,
                )

            created_items = {
                "composer": metadata.get("composer", ""),
                "categories": metadata.get("categories", []),
                "tags": metadata.get("tags", []),
            }
    except ValueError as e:
        raise HttpError(400, str(e))
    except Exception as e:
        raise HttpError(500, f"Error al crear la página: {str(e)}")

    # Construir URLs
    edit_url = f"/cms/pages/{page.id}/edit/"
    if page.live:
        try:
            preview_url = page.get_url(request)
        except Exception:
            preview_url = f"/cms/pages/{page.id}/"
    else:
        preview_url = f"/cms/pages/{page.id}/view_draft/"
    
    page_type_names = {'dictadopage': 'DictadoPage', 'blogpage': 'BlogPage', 'scorepage': 'ScorePage'}
    page_type_name = page_type_names.get(page_type, 'ScorePage')
    message = (
        f"{page_type_name} creada como borrador. Revísala y publica cuando estés listo."
        if not publish_immediately
        else f"{page_type_name} publicada correctamente."
    )

    return AIPublishOut(
        success=True,
        score_page_id=page.id,
        title=page.title,
        edit_url=edit_url,
        preview_url=preview_url,
        message=message,
        created_items=created_items,
    )


# Blog Pages Endpoint
# ------------------------------------------------------------------------------


class BlogPageIn(Schema):
    """Schema de entrada para crear una BlogPage."""

    title: str
    date: date
    intro: str
    body: Optional[str] = ""
    featured_image_id: Optional[int] = None
    is_featured: bool = False
    category_ids: List[int] = []
    tags: List[str] = []
    # Retirado con `MusicTag` (C37b). Se mantiene en el esquema para poder
    # rechazarlo con un 400 explícito: un cliente viejo que lo mandara perdería
    # sus etiquetas en silencio, que es peor que un error.
    tag_ids: List[int] = []
    parent_page_id: Optional[int] = None
    publish_immediately: bool = False
    attachment_ids: List[int] = []
    # Metadatos musicales (2026-08-28). BlogPage sustituye a ScorePage, así que
    # el API tiene que poder ponerlos explícitamente — sin pasar por ai-publish,
    # que los deduciría con un LLM habiendo dato exacto.
    is_protected: bool = False
    is_private: bool = False
    artist: Optional[str] = ""
    reference: Optional[str] = ""
    # Numéricos: MusicXML `fifths`/`mode`, `beats`/`beat-type`, y tempo como
    # número. Guardarlos como texto impedía ordenar, filtrar y exportar.
    key_fifths: Optional[int] = None
    key_mode: Optional[str] = ""
    time_signature_beats: Optional[int] = None
    time_signature_beat_type: Optional[int] = None
    tempo_bpm: Optional[int] = None
    duration_seconds: Optional[int] = None
    # Songsterr y ChordPro (2026-08-31). El id de Songsterr no viaja dentro del
    # .gp, asi que el cliente que sube la tablatura tiene que poder mandarlo.
    songsterr_url: Optional[str] = ""
    chordpro: Optional[str] = ""


class BlogPageOut(Schema):
    """Schema de respuesta para una BlogPage creada."""

    id: int
    title: str
    live: bool
    edit_url: str
    preview_url: str
    is_protected: bool = False
    is_private: bool = False
    owner_id: Optional[int] = None
    artist: str = ""
    reference: str = ""
    key_fifths: Optional[int] = None
    key_mode: str = ""
    time_signature_beats: Optional[int] = None
    time_signature_beat_type: Optional[int] = None
    tempo_bpm: Optional[int] = None
    duration_seconds: Optional[int] = None
    songsterr_url: str = ""
    chordpro: str = ""
    # Cómo se lee, para no obligar al cliente a rehacer el cálculo.
    key_display: str = ""
    time_signature_display: str = ""
    duration_display: str = ""


def _parse_tags(tags: str) -> List[str]:
    """Parse comma-separated tags string into a list of stripped tag names."""
    return [t.strip() for t in tags.split(",") if t.strip()] if tags else []


def _resolve_collection(name: str) -> Collection:
    """Look up a Wagtail Collection by name, raising 400 if not found."""
    try:
        return Collection.objects.get(name=name)
    except Collection.DoesNotExist:
        raise HttpError(400, f"La colección '{name}' no existe.")


def _build_attachments(doc_ids: List[int]):
    """Build StreamField attachments list from document IDs.

    Returns list of (block_type, value) tuples for BlogPage.attachments.
    """
    docs_by_id = {d.id: d for d in DocumentModel.objects.filter(id__in=doc_ids)}
    missing = [did for did in doc_ids if did not in docs_by_id]
    if missing:
        raise HttpError(400, f"Documentos no encontrados: {missing}")
    return [("pdf_score", {"pdf_file": docs_by_id[did]}) for did in doc_ids]


def _get_blog_parent_page(parent_page_id: Optional[int]):
    """Devuelve la página padre para una BlogPage.

    Orden de búsqueda cuando no se especifica parent_page_id:
    1. Primera BlogIndexPage disponible.
    2. Primera MusicLibraryIndexPage disponible.
    3. HttpError 400 si no existe ninguna.
    """
    if parent_page_id is not None:
        # Buscar en los dos tipos de padre permitidos por BlogPage
        parent = (
            BlogIndexPage.objects.filter(id=parent_page_id).first()
            or MusicLibraryIndexPage.objects.filter(id=parent_page_id).first()
        )
        if not parent:
            raise HttpError(
                400,
                f"La página padre con ID {parent_page_id} no existe o no es válida "
                "(debe ser BlogIndexPage o MusicLibraryIndexPage).",
            )
        return parent

    # Búsqueda automática del padre
    parent = BlogIndexPage.objects.first() or MusicLibraryIndexPage.objects.first()
    if not parent:
        raise HttpError(
            400,
            "No existe ninguna BlogIndexPage ni MusicLibraryIndexPage para alojar el artículo.",
        )
    return parent


@router.post("/blog-pages", response=BlogPageOut, tags=["Blog"])
def create_blog_page(request, payload: BlogPageIn):
    """Crear una BlogPage en Wagtail.

    Permite crear artículos de blog con todos sus campos: título, fecha,
    resumen, cuerpo en RichText, imagen destacada, categorías, etiquetas
    y página padre. Se puede publicar inmediatamente o guardar como borrador.

    Args:
        request: Request object.
        payload: Datos del artículo de blog.

    Returns:
        BlogPageOut con id, título, estado live y URLs de edición/preview.

    Raises:
        HttpError 400: Si la página padre no existe o los IDs de categorías/tags son inválidos.
    """
    parent_page = _get_blog_parent_page(payload.parent_page_id)
    featured_image = _get_image(payload.featured_image_id)

    with transaction.atomic():
        page = BlogPage(
            title=payload.title,
            date=payload.date,
            intro=payload.intro,
            body=payload.body or "",
            is_featured=payload.is_featured,
            # El owner es lo que hace efectiva `is_private`: la comprobacion de
            # visibilidad lo usa para decidir quien puede ver la pagina. Las
            # creadas por API nacian sin el, asi que marcarlas privadas no
            # protegia nada (2026-08-29).
            owner=request.user if request.user.is_authenticated else None,
            is_protected=payload.is_protected,
            is_private=payload.is_private,
            artist=payload.artist or "",
            reference=payload.reference or "",
            key_fifths=payload.key_fifths,
            key_mode=payload.key_mode or "",
            time_signature_beats=payload.time_signature_beats,
            time_signature_beat_type=payload.time_signature_beat_type,
            tempo_bpm=payload.tempo_bpm,
            duration_seconds=payload.duration_seconds,
            songsterr_url=payload.songsterr_url or "",
            chordpro=payload.chordpro or "",
            # Wagtail hereda live=True del padre si está publicado;
            # lo sobreescribimos explícitamente para gestionar el estado desde la API.
            live=payload.publish_immediately,
        )
        if featured_image:
            page.featured_image = featured_image
        if payload.attachment_ids:
            page.attachments = _build_attachments(payload.attachment_ids)

        parent_page.add_child(instance=page)

        if payload.category_ids:
            categories = list(
                MusicCategory.objects.filter(id__in=payload.category_ids).distinct()
            )
            if len(categories) != len(set(payload.category_ids)):
                raise HttpError(400, "Alguna categoría proporcionada no existe.")
            page.categories.set(categories)

        _validar_etiquetas(payload)
        if payload.tags:
            aplicar_etiquetas(page, payload.tags)

        revision = page.save_revision()
        if payload.publish_immediately:
            revision.publish()
            # Refrescar desde DB para que page.live esté actualizado
            page.refresh_from_db()

    edit_url = f"/cms/pages/{page.id}/edit/"
    if page.live:
        try:
            preview_url = page.get_url(request) or f"/cms/pages/{page.id}/"
        except Exception:
            preview_url = f"/cms/pages/{page.id}/"
    else:
        preview_url = f"/cms/pages/{page.id}/view_draft/"

    return BlogPageOut(
        id=page.id,
        title=page.title,
        live=page.live,
        edit_url=edit_url,
        preview_url=preview_url,
        is_protected=page.is_protected,
        is_private=page.is_private,
        owner_id=page.owner_id,
        artist=page.artist,
        reference=page.reference,
        key_fifths=page.key_fifths,
        key_mode=page.key_mode,
        time_signature_beats=page.time_signature_beats,
        time_signature_beat_type=page.time_signature_beat_type,
        tempo_bpm=page.tempo_bpm,
        duration_seconds=page.duration_seconds,
        songsterr_url=page.songsterr_url,
        chordpro=page.chordpro,
        key_display=page.key_display,
        time_signature_display=page.time_signature_display,
        duration_display=page.duration_display,
    )


class BlogPageUpdateIn(Schema):
    """Schema de entrada para actualizar una BlogPage (todos los campos opcionales)."""

    title: Optional[str] = None
    date: Optional[date] = None
    intro: Optional[str] = None
    body: Optional[str] = None
    featured_image_id: Optional[int] = None
    is_featured: Optional[bool] = None
    category_ids: Optional[List[int]] = None
    tags: Optional[List[str]] = None
    # Retirado con `MusicTag` (C37b). Ver arriba.
    tag_ids: Optional[List[int]] = None
    publish_immediately: Optional[bool] = None
    attachment_ids: Optional[List[int]] = None
    # Metadatos musicales (2026-08-28). None = no tocar; "" = borrar.
    is_protected: Optional[bool] = None
    is_private: Optional[bool] = None
    artist: Optional[str] = None
    reference: Optional[str] = None
    key_fifths: Optional[int] = None
    key_mode: Optional[str] = None
    time_signature_beats: Optional[int] = None
    time_signature_beat_type: Optional[int] = None
    tempo_bpm: Optional[int] = None
    duration_seconds: Optional[int] = None
    songsterr_url: Optional[str] = None
    chordpro: Optional[str] = None


@router.put("/blog-pages/{page_id}", response=BlogPageOut, tags=["Blog"])
def update_blog_page(request, page_id: int, payload: BlogPageUpdateIn):
    """Actualizar una BlogPage existente en Wagtail.

    Acepta campos parciales — sólo se actualizan los campos enviados.

    Args:
        request: Request object.
        page_id: ID de la BlogPage a actualizar.
        payload: Campos a actualizar.

    Returns:
        BlogPageOut con id, título, estado live y URLs de edición/preview.

    Raises:
        HttpError 404: Si la BlogPage no existe.
        HttpError 400: Si los IDs de categorías/tags/imagen son inválidos.
    """
    try:
        page = BlogPage.objects.get(id=page_id)
    except BlogPage.DoesNotExist:
        raise HttpError(404, f"La BlogPage con ID {page_id} no existe.")

    with transaction.atomic():
        if payload.title is not None:
            page.title = payload.title
        if payload.date is not None:
            page.date = payload.date
        if payload.intro is not None:
            page.intro = payload.intro
        if payload.body is not None:
            page.body = payload.body
        if payload.featured_image_id is not None:
            page.featured_image = _get_image(payload.featured_image_id)
        if payload.is_featured is not None:
            page.is_featured = payload.is_featured
        if payload.attachment_ids is not None:
            page.attachments = _build_attachments(payload.attachment_ids)
        if payload.is_protected is not None:
            page.is_protected = payload.is_protected
        if payload.is_private is not None:
            page.is_private = payload.is_private
            # Hacer privada una pagina huerfana sin darle dueno la dejaria
            # accesible por URL directa. Se adopta al vuelo.
            if payload.is_private and page.owner is None and request.user.is_authenticated:
                page.owner = request.user
        for _campo in ("artist", "reference", "key_fifths", "key_mode",
                       "time_signature_beats", "time_signature_beat_type",
                       "tempo_bpm", "duration_seconds",
                       "songsterr_url", "chordpro"):
            _valor = getattr(payload, _campo)
            if _valor is not None:
                setattr(page, _campo, _valor)

        if payload.category_ids is not None:
            categories = list(
                MusicCategory.objects.filter(id__in=payload.category_ids).distinct()
            )
            if len(categories) != len(set(payload.category_ids)):
                raise HttpError(400, "Alguna categoría proporcionada no existe.")
            page.categories.set(categories)

        _validar_etiquetas(payload)
        if payload.tags is not None:
            aplicar_etiquetas(page, payload.tags)

        revision = page.save_revision()
        if payload.publish_immediately:
            revision.publish()
            page.refresh_from_db()

    edit_url = f"/cms/pages/{page.id}/edit/"
    if page.live:
        try:
            preview_url = page.get_url(request) or f"/cms/pages/{page.id}/"
        except Exception:
            preview_url = f"/cms/pages/{page.id}/"
    else:
        preview_url = f"/cms/pages/{page.id}/view_draft/"

    return BlogPageOut(
        id=page.id,
        title=page.title,
        live=page.live,
        edit_url=edit_url,
        preview_url=preview_url,
        is_protected=page.is_protected,
        is_private=page.is_private,
        owner_id=page.owner_id,
        artist=page.artist,
        reference=page.reference,
        key_fifths=page.key_fifths,
        key_mode=page.key_mode,
        time_signature_beats=page.time_signature_beats,
        time_signature_beat_type=page.time_signature_beat_type,
        tempo_bpm=page.tempo_bpm,
        duration_seconds=page.duration_seconds,
        songsterr_url=page.songsterr_url,
        chordpro=page.chordpro,
        key_display=page.key_display,
        time_signature_display=page.time_signature_display,
        duration_display=page.duration_display,
    )


class DeleteOut(Schema):
    """Schema de respuesta para eliminación."""

    success: bool
    message: str


@router.delete("/blog-pages/{page_id}", response=DeleteOut, tags=["Blog"])
def delete_blog_page(request, page_id: int):
    """Eliminar una BlogPage de Wagtail.

    Args:
        request: Request object.
        page_id: ID de la BlogPage a eliminar.

    Returns:
        DeleteOut confirmando la eliminación.

    Raises:
        HttpError 404: Si la BlogPage no existe.
    """
    try:
        page = BlogPage.objects.get(id=page_id)
    except BlogPage.DoesNotExist:
        raise HttpError(404, f"La BlogPage con ID {page_id} no existe.")

    title = page.title
    page.delete()

    return DeleteOut(success=True, message=f"BlogPage '{title}' (ID {page_id}) eliminada.")


# Image Upload Endpoint
# ------------------------------------------------------------------------------


class ImageUploadOut(Schema):
    """Response schema for image upload"""

    id: int
    title: str


@router.post("/upload-image", response=ImageUploadOut)
def upload_image(
    request,
    title: str = Form(..., description="Título de la imagen"),
    file: UploadedFile = File(..., description="Archivo de imagen"),
    tags: str = Form("", description="Tags separados por coma (opcional)"),
    collection: str = Form("", description="Nombre de la colección (opcional)"),
):
    """
    Upload an image to Wagtail image library.
    """
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/avif"}
    if file.content_type not in allowed_types:
        raise HttpError(
            400,
            f"Tipo de archivo no válido: {file.content_type}. "
            f"Se esperaba una imagen ({', '.join(allowed_types)}).",
        )

    tag_list = _parse_tags(tags)

    image = ImageModel(
        title=title,
        file=file,
        uploaded_by_user=request.user,
    )

    if collection:
        image.collection = _resolve_collection(collection)

    image.save()

    if tag_list:
        image.tags.add(*tag_list)

    return ImageUploadOut(id=image.id, title=image.title)


# Document Upload Endpoint
# ------------------------------------------------------------------------------


class DocumentUploadOut(Schema):
    """Response schema for document upload"""

    id: int
    title: str


@router.post("/upload-document", response=DocumentUploadOut)
def upload_document(
    request,
    title: str = Form(..., description="Título del documento"),
    file: UploadedFile = File(..., description="Archivo del documento"),
    tags: str = Form("", description="Tags separados por coma (opcional)"),
    collection: str = Form("", description="Nombre de la colección (opcional)"),
):
    """
    Upload a document to Wagtail document library.
    """
    tag_list = _parse_tags(tags)

    document = DocumentModel(
        title=title,
        file=file,
        uploaded_by_user=request.user,
    )

    if collection:
        document.collection = _resolve_collection(collection)

    document.save()

    if tag_list:
        document.tags.add(*tag_list)

    return DocumentUploadOut(id=document.id, title=document.title)


# ---------------------------------------------------------------------------
# Libro de estudio — capítulos (2026-08-28)
#
# `capitulos` es un StreamField de PageChooserBlock, así que hasta ahora la
# única forma de añadir una página al libro era arrastrarla a mano en el admin
# de Wagtail. Con BlogPage sustituyendo a ScorePage y repertorios de decenas de
# canciones, eso no escala.
# ---------------------------------------------------------------------------

CAPITULO_TIPOS_VALIDOS = ("BlogPage", "ScorePage", "DictadoPage")


class ChaptersIn(Schema):
    """Schema de entrada para añadir capítulos a un LibroDeEstudioPage."""

    page_ids: List[int]
    # Por defecto añade al final y conserva lo que ya hubiera: un libro con
    # capítulos ya ordenados a mano no debe perderlos por una llamada de API.
    replace: bool = False
    publish_immediately: bool = False


class ChaptersOut(Schema):
    id: int
    title: str
    live: bool
    total_capitulos: int
    anadidos: List[int]
    ya_estaban: List[int]
    edit_url: str


@router.post("/study-books/{page_id}/chapters", response=ChaptersOut, tags=["Libro de estudio"])
def add_study_book_chapters(request, page_id: int, payload: ChaptersIn):
    """Añadir páginas como capítulos de un libro de estudio.

    El orden de `page_ids` manda: es el orden en que saldrán a estudiar.
    Las páginas que ya fueran capítulos se ignoran en vez de duplicarse, así
    que reintentar una llamada a medias es seguro.
    """
    from .models import LibroDeEstudioPage

    try:
        libro = LibroDeEstudioPage.objects.get(id=page_id)
    except LibroDeEstudioPage.DoesNotExist:
        raise HttpError(404, f"No hay ningún libro de estudio con id {page_id}.")

    if not payload.page_ids:
        raise HttpError(400, "`page_ids` está vacío: no hay nada que añadir.")

    paginas = WagtailPage.objects.filter(id__in=payload.page_ids).specific()
    por_id = {p.id: p for p in paginas}

    faltan = [i for i in payload.page_ids if i not in por_id]
    if faltan:
        raise HttpError(400, f"Estas páginas no existen: {faltan}.")

    # Default-deny sobre el tipo: el bloque solo acepta tres, y meter otro
    # dejaría el StreamField ilegible en el admin en vez de fallar aquí.
    invalidas = {
        i: type(por_id[i]).__name__
        for i in payload.page_ids
        if type(por_id[i]).__name__ not in CAPITULO_TIPOS_VALIDOS
    }
    if invalidas:
        raise HttpError(
            400,
            f"Tipos no admitidos como capítulo: {invalidas}. "
            f"Solo valen {', '.join(CAPITULO_TIPOS_VALIDOS)}.",
        )

    with transaction.atomic():
        if payload.replace:
            existentes = []
            libro.capitulos = []
        else:
            existentes = [b.value.id for b in libro.capitulos if b.value]

        anadidos, ya_estaban = [], []
        for i in payload.page_ids:
            if i in existentes or i in anadidos:
                ya_estaban.append(i)
                continue
            libro.capitulos.append(("pagina", por_id[i]))
            anadidos.append(i)

        revision = libro.save_revision()
        if payload.publish_immediately:
            revision.publish()
            libro.refresh_from_db()

    return ChaptersOut(
        id=libro.id,
        title=libro.title,
        live=libro.live,
        total_capitulos=len(libro.capitulos),
        anadidos=anadidos,
        ya_estaban=ya_estaban,
        edit_url=f"/cms/pages/{libro.id}/edit/",
    )


class LibroVisibilidadIn(Schema):
    """Visibilidad de un libro de estudio. `None` = no tocar."""

    is_protected: Optional[bool] = None
    is_private: Optional[bool] = None
    publish_immediately: bool = True


class LibroVisibilidadOut(Schema):
    id: int
    title: str
    live: bool
    is_protected: bool
    is_private: bool
    owner_id: Optional[int] = None


@router.post("/study-books/{page_id}/visibility", response=LibroVisibilidadOut, tags=["Libro de estudio"])
def set_study_book_visibility(request, page_id: int, payload: LibroVisibilidadIn):
    """Marcar un libro de estudio como protegido o privado.

    Privado exige dueño: sin él la comprobación de visibilidad no llega a
    ejecutarse y el libro se serviría por URL directa. Si el libro no tiene
    dueño, lo adopta quien hace la llamada.
    """
    from .models import LibroDeEstudioPage

    try:
        libro = LibroDeEstudioPage.objects.get(id=page_id)
    except LibroDeEstudioPage.DoesNotExist:
        raise HttpError(404, f"No hay ningún libro de estudio con id {page_id}.")

    with transaction.atomic():
        if payload.is_protected is not None:
            libro.is_protected = payload.is_protected
        if payload.is_private is not None:
            libro.is_private = payload.is_private
            if payload.is_private and libro.owner is None:
                if not request.user.is_authenticated:
                    raise HttpError(
                        400,
                        "No se puede marcar privado un libro sin dueño desde una "
                        "petición sin usuario: quedaría accesible por URL directa.",
                    )
                libro.owner = request.user

        revision = libro.save_revision()
        if payload.publish_immediately:
            revision.publish()
            libro.refresh_from_db()

    return LibroVisibilidadOut(
        id=libro.id,
        title=libro.title,
        live=libro.live,
        is_protected=libro.is_protected,
        is_private=libro.is_private,
        owner_id=libro.owner_id,
    )
