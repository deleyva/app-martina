"""
Servicios de la programación didáctica.

Núcleo: dado que cada ClassSessionItem guarda (content_type, object_id) del
elemento y la página de origen, podemos calcular qué parte de un artículo,
partitura o capítulo ha visto ya cada grupo — incluso retroactivamente con
el historial de sesiones existente.
"""

from django.contrib.contenttypes.models import ContentType

from clases.models import ClassSessionItem


def _element(obj, kind, title):
    """Normalizar un elemento a dict con clave estable."""
    ct = ContentType.objects.get_for_model(obj, for_concrete_model=True)
    return {
        "key": f"{ct.model}:{obj.pk}",
        "content_type_id": ct.pk,
        "object_id": obj.pk,
        "kind": kind,
        "title": title or str(obj),
        "object": obj,
    }


def get_page_elements(page):
    """
    Enumerar los elementos "añadibles a sesión" de una página.
    Soporta BlogPage (attachments) y ScorePage (content).
    Devuelve lista de dicts (ver _element).
    """
    specific = page.specific if hasattr(page, "specific") else page
    model = type(specific).__name__.lower()
    elements = []

    if model == "blogpage":
        cache = specific._parse_attachments()
        for sv in cache["pdfs"]:
            doc = sv.get("pdf_file")
            if doc:
                elements.append(_element(doc, "pdf", doc.title))
        for sv in cache["audios"]:
            doc = sv.get("audio_file")
            if doc:
                elements.append(_element(doc, "audio", doc.title))
        for sv in cache["videos"]:
            doc = sv.get("video_file")
            if doc:
                elements.append(_element(doc, "video", doc.title))
        for sv in cache["images"]:
            img = sv.get("image")
            if img:
                elements.append(_element(img, "image", img.title))

    elif model == "scorepage":
        for block in specific.content:
            value = block.value
            if block.block_type == "pdf_score":
                doc = value.get("pdf_file") if hasattr(value, "get") else None
                if doc:
                    elements.append(_element(doc, "pdf", doc.title))
            elif block.block_type == "audio":
                doc = value.get("audio_file") if hasattr(value, "get") else None
                if doc:
                    elements.append(_element(doc, "audio", doc.title))
            elif block.block_type == "image":
                img = value.get("image") if hasattr(value, "get") else None
                if img:
                    elements.append(_element(img, "image", img.title))
            elif block.block_type == "embed":
                url = getattr(value, "url", None)
                if url:
                    from wagtail.embeds.models import Embed

                    embed = Embed.objects.filter(url=url).first()
                    if embed:
                        elements.append(_element(embed, "embed", url))

    # Deduplicar por clave conservando orden
    seen, unique = set(), []
    for el in elements:
        if el["key"] not in seen:
            seen.add(el["key"])
            unique.append(el)
    return unique


def get_seen_keys(group, page=None):
    """
    Claves "modelo:pk" de todos los elementos que el grupo ya ha visto en
    sesiones de clase. Si se pasa page, no se filtra por source_page a
    propósito: si el grupo vio ese documento en cualquier sesión, cuenta.
    """
    qs = ClassSessionItem.objects.filter(session__group=group).select_related(
        "content_type"
    )
    return {f"{item.content_type.model}:{item.object_id}" for item in qs}


def recompute_coverage(group, page):
    """Recalcular la cobertura de una página para un grupo y guardarla."""
    from .models import ContentCoverage

    specific = page.specific if hasattr(page, "specific") else page
    elements = get_page_elements(specific)
    seen_keys = get_seen_keys(group)

    seen_elements = [el["key"] for el in elements if el["key"] in seen_keys]

    # ¿Se presentó la página completa como item de sesión?
    page_ct = ContentType.objects.get_for_model(specific, for_concrete_model=True)
    page_presented = ClassSessionItem.objects.filter(
        session__group=group,
        content_type__model=page_ct.model,
        object_id=specific.pk,
    ).exists()
    # También cuenta la ct genérica "page" de wagtail por si acaso
    if not page_presented:
        page_presented = ClassSessionItem.objects.filter(
            session__group=group,
            content_type__model="page",
            object_id=specific.pk,
        ).exists()

    last_session_item = (
        ClassSessionItem.objects.filter(session__group=group, source_page=page)
        .select_related("session")
        .order_by("-session__date")
        .first()
    )

    coverage, _ = ContentCoverage.objects.update_or_create(
        group=group,
        content_type=page_ct,
        object_id=specific.pk,
        defaults={
            "elements_total": len(elements),
            "elements_seen": len(seen_elements),
            "seen_element_keys": seen_elements,
            "page_presented": page_presented,
            "last_session": last_session_item.session if last_session_item else None,
        },
    )
    return coverage


def update_coverage_for_session(session):
    """Recalcular cobertura de todas las páginas de origen usadas en una sesión."""
    pages = set()
    for item in session.items.select_related("source_page"):
        if item.source_page_id:
            pages.add(item.source_page)
        # El item puede SER una página (artículo completo en la sesión)
        if item.content_type.model in ("blogpage", "scorepage", "dictadopage"):
            obj = item.content_object
            if obj:
                pages.add(obj)
    for page in pages:
        recompute_coverage(session.group, page)


def get_pending_elements(group, page):
    """Elementos de una página que el grupo aún no ha visto."""
    elements = get_page_elements(page)
    seen_keys = get_seen_keys(group)
    return [el for el in elements if el["key"] not in seen_keys]


def create_session_from_plan_item(plan_item, teacher, date, title=None):
    """
    Crear una ClassSession prellenada con los elementos pendientes del item.
    Devuelve la sesión creada.
    """
    from clases.models import ClassSession

    page = plan_item.content_object
    session = ClassSession.objects.create(
        teacher=teacher,
        group=plan_item.plan.group,
        date=date,
        title=title or plan_item.get_content_title(),
        metadata={"plan_item_id": plan_item.pk, "plan_id": plan_item.plan_id},
    )
    pending = get_pending_elements(plan_item.plan.group, page) if page else []
    for order, el in enumerate(pending):
        ClassSessionItem.objects.create(
            session=session,
            content_type_id=el["content_type_id"],
            object_id=el["object_id"],
            source_page=page,
            order=order,
        )
    return session
