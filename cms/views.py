from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
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


@login_required
def score_embed_html(request):
    score_id = request.GET.get("score_id")
    embed_url = request.GET.get("url")

    score = get_object_or_404(ScorePage, pk=score_id)
    embed_html = score.get_embed_html_for_url(embed_url)
    if not embed_html:
        raise Http404

    return HttpResponse(embed_html)


@login_required
def ai_publish_form(request):
    """
    Vista del formulario de publicación asistida por IA.

    Permite subir archivos musicales (PDFs, audios, imágenes, MIDI) junto con
    una descripción en lenguaje natural. La IA procesa la descripción y crea
    automáticamente una ScorePage en Wagtail.
    """
    return render(request, "cms/ai_publish_form.html")


from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from .models import MusicCategory, ScorePageCategory


@staff_member_required
def order_scores_view(request):
    """
    Vista para ordenar ScorePages dentro de categorías.
    Solo accesible por staff/profesores.
    """
    categories = MusicCategory.objects.all().prefetch_related(
        "category_scores__score_page"
    )

    # Organizar datos para el template
    categories_data = []
    for category in categories:
        scores = category.category_scores.all().order_by("sort_order")
        if scores.exists():  # Solo mostrar categorías con ScorePages
            scores_list = []
            for relation in scores:
                score_page = relation.score_page

                # Obtener primera imagen o PDF como preview
                first_image = None
                first_pdf_url = None

                # 1. Intentar obtener primera imagen
                images = score_page.get_images()
                if images and len(images) > 0:
                    first_image_block = images[0]
                    first_image = first_image_block.get('image')

                # 2. Si no hay imagen, obtener primer PDF
                if not first_image:
                    pdf_blocks = score_page.get_pdf_blocks()
                    if pdf_blocks and len(pdf_blocks) > 0:
                        first_pdf_block = pdf_blocks[0]
                        pdf_file = first_pdf_block.get('pdf_file')
                        if pdf_file:
                            first_pdf_url = pdf_file.url

                scores_list.append({
                    "id": relation.id,  # ID de ScorePageCategory
                    "score_id": score_page.id,
                    "title": score_page.title,
                    "sort_order": relation.sort_order,
                    "first_image": first_image,  # Objeto Wagtail Image o None
                    "first_pdf_url": first_pdf_url,  # URL del PDF o None
                    "url": score_page.get_url(request),  # URL de la ScorePage
                })

            categories_data.append({
                "id": category.id,
                "name": category.name,
                "full_path": category.full_path,
                "scores": scores_list,
            })

    return render(
        request,
        "cms/order_scores.html",
        {
            "categories": categories_data,
        },
    )


from django.views.decorators.csrf import ensure_csrf_cookie


@staff_member_required
@require_POST
def update_scores_order(request):
    """
    Endpoint API para actualizar el orden de ScorePages en una categoría.
    Recibe: {"category_id": 1, "order": [relation_id1, relation_id2, ...]}
    """
    import logging
    logger = logging.getLogger(__name__)

    # Verificar que el request tenga permisos
    if not request.user.is_staff:
        logger.warning(f"Usuario sin permisos intentó actualizar orden: {request.user}")
        return JsonResponse({"error": "Permiso denegado"}, status=403)

    try:
        data = json.loads(request.body)
        category_id = data.get("category_id")
        new_order = data.get("order", [])  # Lista de IDs de ScorePageCategory

        logger.info(f"Actualizando orden - Categoría: {category_id}, Orden: {new_order}")

        if not category_id or not new_order:
            logger.error(f"Datos inválidos - category_id: {category_id}, order: {new_order}")
            return JsonResponse({"error": "Datos inválidos"}, status=400)

        # Actualizar sort_order de cada ScorePageCategory
        updated_count = 0
        for index, relation_id in enumerate(new_order):
            result = ScorePageCategory.objects.filter(
                id=relation_id, category_id=category_id
            ).update(sort_order=index)
            updated_count += result
            logger.debug(f"Actualizado relation_id={relation_id} a sort_order={index}, affected={result}")

        logger.info(f"Orden actualizado exitosamente. Registros actualizados: {updated_count}")
        return JsonResponse({"success": True, "message": "Orden actualizado", "updated": updated_count})

    except json.JSONDecodeError as e:
        logger.error(f"Error parseando JSON: {e}")
        return JsonResponse({"error": "JSON inválido"}, status=400)
    except Exception as e:
        logger.exception(f"Error actualizando orden: {e}")
        return JsonResponse({"error": str(e)}, status=500)
