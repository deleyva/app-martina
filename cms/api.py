from datetime import date
from typing import List, Optional

from django.db import transaction
from django.utils import timezone
from ninja import Router, Schema, File, Form
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja.security import django_auth
from wagtail.images import get_image_model

from api_keys.auth import DatabaseApiKey
from .models import (
    MusicCategory,
    MusicLibraryIndexPage,
    MusicTag,
    TestPage,
)
from .services import AIMetadataExtractor, ContentPublisher


router = Router(tags=["CMS Tests"], auth=[DatabaseApiKey(), django_auth])
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
        if payload.tag_ids:
            tags = list(MusicTag.objects.filter(id__in=payload.tag_ids).distinct())
            if len(tags) != len(set(payload.tag_ids)):
                raise HttpError(400, "Alguna etiqueta proporcionada no existe.")
            page.tags.set(tags)

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
    page_type: str = Form("scorepage", description="Tipo de página: 'scorepage' o 'dictadopage'"),
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
    
    page_type_name = "DictadoPage" if page_type == 'dictadopage' else "ScorePage"
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
