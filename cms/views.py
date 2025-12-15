from django.http import Http404
from django.shortcuts import render
from django.core.paginator import Paginator
from .models import ScorePage

from .models import HelpIndexPage, HelpVideoPage


def filtered_scores_view(request):
    """
    Vista para mostrar ScorePages filtradas por etiquetas de documentos.

    Parámetros URL:
    - tags: Lista de nombres de etiquetas separadas por coma
    - categories: Lista de nombres de categorías separadas por coma
    - difficulty: Nivel de dificultad específico
    - document_tags: Etiquetas de documentos (PDFs/Audios)

    Ejemplo: /scores/filtered/?document_tags=3/8,lectura-rítmica&categories=ejercicios
    """

    # Obtener parámetros de filtrado
    tag_names = (
        request.GET.get("tags", "").split(",") if request.GET.get("tags") else []
    )
    category_names = (
        request.GET.get("categories", "").split(",")
        if request.GET.get("categories")
        else []
    )
    difficulty_filter = request.GET.get("difficulty", "")

    # Limpiar nombres (eliminar espacios)
    tag_names = [name.strip() for name in tag_names if name.strip()]
    category_names = [name.strip() for name in category_names if name.strip()]

    # Comenzar con todas las ScorePages publicadas
    scores = ScorePage.objects.live().order_by("-first_published_at")

    # Filtrar por etiquetas de página
    if tag_names:
        for tag_name in tag_names:
            scores = scores.filter(tags__name__iexact=tag_name)

    # Filtrar por categorías de página
    if category_names:
        for category_name in category_names:
            scores = scores.filter(categories__name__iexact=category_name)

    # Filtrar por etiquetas de documentos (PDFs y Audios)
    document_tag_names = (
        request.GET.get("document_tags", "").split(",")
        if request.GET.get("document_tags")
        else []
    )
    document_tag_names = [name.strip() for name in document_tag_names if name.strip()]

    if document_tag_names:
        # Filtrar scores que tengan documentos con las etiquetas especificadas
        filtered_score_ids = []
        for score in scores:
            has_matching_tags = False

            # Verificar PDFs
            pdf_blocks = score.get_pdf_blocks()
            audio_blocks = score.get_audios()

            # Buscar en PDFs
            for pdf_block in pdf_blocks:
                # Acceder al archivo PDF usando la clave del diccionario
                if "pdf_file" in pdf_block and pdf_block["pdf_file"]:
                    try:
                        pdf_document = pdf_block["pdf_file"]
                        if hasattr(pdf_document, "tags"):
                            pdf_tags = [
                                tag.name.lower() for tag in pdf_document.tags.all()
                            ]
                            # Verificar si CUALQUIERA de las etiquetas buscadas está presente
                            if any(
                                tag_name.lower() in pdf_tags
                                for tag_name in document_tag_names
                            ):
                                has_matching_tags = True
                                break
                    except AttributeError:
                        continue

            # Buscar en Audios si no se encontró en PDFs
            if not has_matching_tags:
                for audio_block in audio_blocks:
                    if "audio_file" in audio_block and audio_block["audio_file"]:
                        try:
                            audio_document = audio_block["audio_file"]
                            if hasattr(audio_document, "tags"):
                                audio_tags = [
                                    tag.name.lower()
                                    for tag in audio_document.tags.all()
                                ]
                                # Verificar si CUALQUIERA de las etiquetas buscadas está presente
                                if any(
                                    tag_name.lower() in audio_tags
                                    for tag_name in document_tag_names
                                ):
                                    has_matching_tags = True
                                    break
                        except AttributeError:
                            continue

            # Buscar en Imágenes si no se encontró en PDFs ni Audios
            if not has_matching_tags:
                image_blocks = score.get_images()
                for image_block in image_blocks:
                    if "image" in image_block and image_block["image"]:
                        try:
                            image_document = image_block["image"]
                            if hasattr(image_document, "tags"):
                                image_tags = [
                                    tag.name.lower()
                                    for tag in image_document.tags.all()
                                ]
                                # Verificar si CUALQUIERA de las etiquetas buscadas está presente
                                if any(
                                    tag_name.lower() in image_tags
                                    for tag_name in document_tag_names
                                ):
                                    has_matching_tags = True
                                    break
                        except AttributeError:
                            continue

            if has_matching_tags:
                filtered_score_ids.append(score.id)

        scores = scores.filter(id__in=filtered_score_ids)

    # Filtrar por dificultad de documentos
    if difficulty_filter:
        filtered_score_ids = []
        for score in scores:
            pdf_blocks = score.get_pdf_blocks()
            audio_blocks = score.get_audios()
            image_blocks = score.get_images()

            has_matching_difficulty = False

            # Verificar dificultad en PDFs, Audios e Imágenes
            for block in pdf_blocks + audio_blocks + image_blocks:
                if (
                    hasattr(block, "difficulty_level")
                    and block.difficulty_level == difficulty_filter
                ):
                    has_matching_difficulty = True
                    break

            if has_matching_difficulty:
                filtered_score_ids.append(score.id)

        scores = scores.filter(id__in=filtered_score_ids)

    # Paginación
    paginator = Paginator(scores, 12)  # 12 scores por página
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Preparar contexto
    context = {
        "scores": page_obj,
        "filter_tags": tag_names,
        "filter_categories": category_names,
        "filter_document_tags": document_tag_names,
        "filter_difficulty": difficulty_filter,
        "total_results": scores.count(),
        "page_title": "Partituras Filtradas",
    }

    return render(request, "cms/filtered_scores.html", context)


def help_index(request):
    page = HelpIndexPage.for_request(request)
    if not page:
        raise Http404
    return page.specific.serve(request)


def help_video(request, slug):
    page = HelpVideoPage.for_request_and_slug(request, slug)
    if not page:
        raise Http404
    return page.specific.serve(request)
