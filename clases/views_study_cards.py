from datetime import date

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods

from wagtail.images import get_image_model

from clases.models import (
    Enrollment,
    Group,
    StudyCardBatch,
    StudyCardItem,
    StudyCardPickup,
)
from clases.services.card_codes import generate_codes_for_page
from clases.services.card_ocr import ocr_registration_sheet
from clases.services.card_pdf import generate_cards_pdf, generate_registration_sheet
from clases.services.card_suggestions import get_suggestions_for_group
from clases.views import is_staff
from cms.models import BlogIndexPage, BlogPage

TAG_IMPRIMIBLE = "imprimible"


def _has_tag(image, tag_name):
    return tag_name in {t.name for t in image.tags.all()}


def _get_book_stats(book):
    """Get image stats for a book: total and imprimible counts."""
    chapters = book.get_children().type(BlogPage).specific().order_by("path")
    total = 0
    imprimible = 0
    for ch in chapters:
        images = ch.get_images()
        total += len(images)
        imprimible += sum(1 for img in images if _has_tag(img, TAG_IMPRIMIBLE))
    return {"total": total, "imprimible": imprimible, "chapters": len(chapters)}


def _find_item_by_code(code, group):
    """Find or create a StudyCardItem for a code within a group's batches."""
    # Try existing items first
    item = StudyCardItem.objects.filter(
        code=code, batch__group=group
    ).select_related("batch").first()
    if item:
        return item, None

    # Code not in any batch — find image from CMS and create batch + item
    all_books = list(BlogIndexPage.objects.live())
    for book in all_books:
        chapters = book.get_children().type(BlogPage).specific().order_by("path")
        for chapter in chapters:
            codes = generate_codes_for_page(chapter, all_books=all_books)
            for img, generated_code in codes:
                if generated_code == code:
                    # Found it — create auto-batch and item
                    batch, _ = StudyCardBatch.objects.get_or_create(
                        group=group,
                        title=f"Auto — {book.title}",
                        defaults={"created_by_id": 1},  # Will be overridden
                    )
                    item = StudyCardItem.objects.create(
                        batch=batch,
                        image=img,
                        source_page=chapter,
                        code=code,
                        position=0,
                    )
                    return item, None

    return None, f"Código '{code}' no encontrado en ningún libro"


# =============================================================================
# DASHBOARD
# =============================================================================


@login_required
@user_passes_test(is_staff)
def dashboard(request):
    books = BlogIndexPage.objects.live().order_by("title")
    book_data = []
    for book in books:
        stats = _get_book_stats(book)
        if stats["total"] > 0:
            book_data.append({"book": book, **stats})

    # Groups where current user is teacher
    groups = Group.objects.filter(teachers=request.user).order_by("name")
    group_data = []
    for group in groups:
        student_count = Enrollment.objects.filter(group=group, is_active=True).count()
        pickup_count = StudyCardPickup.objects.filter(card_item__batch__group=group).count()
        group_data.append({
            "group": group,
            "student_count": student_count,
            "pickup_count": pickup_count,
        })

    return render(request, "clases/study_cards/dashboard.html", {
        "books": book_data,
        "groups": group_data,
    })


# =============================================================================
# BOOK BROWSER (existing)
# =============================================================================


@login_required
@user_passes_test(is_staff)
def book_browser(request, book_id):
    book = get_object_or_404(BlogIndexPage, pk=book_id)
    chapters = list(book.get_children().type(BlogPage).specific().order_by("path"))

    all_books = list(BlogIndexPage.objects.live())
    chapter_data = []
    total_imprimible = 0

    for ch_idx, chapter in enumerate(chapters, start=1):
        codes = generate_codes_for_page(chapter, all_books=all_books)
        if not codes:
            continue
        images_with_tag = []
        for img, code in codes:
            is_imprimible = _has_tag(img, TAG_IMPRIMIBLE)
            if is_imprimible:
                total_imprimible += 1
            images_with_tag.append({
                "image": img,
                "code": code,
                "is_imprimible": is_imprimible,
            })
        chapter_data.append({
            "index": ch_idx,
            "page": chapter,
            "images": images_with_tag,
        })

    return render(request, "clases/study_cards/book_browser.html", {
        "book": book,
        "chapters": chapter_data,
        "total_imprimible": total_imprimible,
    })


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def toggle_tag(request, image_id):
    Image = get_image_model()
    image = get_object_or_404(Image, pk=image_id)

    if image.tags.filter(name=TAG_IMPRIMIBLE).exists():
        image.tags.remove(TAG_IMPRIMIBLE)
        is_imprimible = False
        delta = -1
    else:
        image.tags.add(TAG_IMPRIMIBLE)
        is_imprimible = True
        delta = 1
    image.save()

    code = request.POST.get("code", "???")
    book_id = request.POST.get("book_id")

    try:
        prev_count = int(request.POST.get("current_count", 0))
    except (ValueError, TypeError):
        prev_count = 0
    total_imprimible = max(0, prev_count + delta)

    return render(request, "clases/study_cards/partials/image_card.html", {
        "item": {"image": image, "code": code, "is_imprimible": is_imprimible},
        "total_imprimible": total_imprimible,
        "book_id": book_id,
        "oob_counter": True,
    })


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def generate_pdf(request, book_id):
    book = get_object_or_404(BlogIndexPage, pk=book_id)
    chapters = book.get_children().type(BlogPage).specific().order_by("path")
    all_books = list(BlogIndexPage.objects.live())

    all_items = []
    all_codes_by_chapter = []
    for chapter in chapters:
        codes = generate_codes_for_page(chapter, all_books=all_books, tag=TAG_IMPRIMIBLE)
        all_items.extend(codes)
        # Also collect all images for fill candidates
        all_codes_by_chapter.append(
            generate_codes_for_page(chapter, all_books=all_books)
        )

    if not all_items:
        return HttpResponse(
            '<div class="alert alert-warning">No hay imágenes marcadas como imprimible.</div>',
            status=200,
        )

    # Build fill candidates: non-imprimible images from the same book
    selected_ids = {img.pk for img, _ in all_items}
    fill_items = []
    for chapter_codes in all_codes_by_chapter:
        for img, code in chapter_codes:
            if img.pk not in selected_ids:
                fill_items.append((img, code))

    pdf_bytes = generate_cards_pdf(all_items, fill_items=fill_items)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    safe_title = book.title.replace(" ", "_")[:40]
    response["Content-Disposition"] = f'attachment; filename="tarjetas_{safe_title}.pdf"'
    return response


# =============================================================================
# GROUP TRACKING
# =============================================================================


@login_required
@user_passes_test(is_staff)
def group_tracking(request, group_id):
    group = get_object_or_404(Group, pk=group_id)

    students = (
        Enrollment.objects.filter(group=group, is_active=True)
        .select_related("user")
        .order_by("user__name")
    )

    pickups = (
        StudyCardPickup.objects.filter(card_item__batch__group=group)
        .select_related("card_item", "student")
        .order_by("-picked_up_at", "-id")[:50]
    )

    suggestions = get_suggestions_for_group(group, max_per_student=3)

    return render(request, "clases/study_cards/group_tracking.html", {
        "group": group,
        "students": students,
        "pickups": pickups,
        "suggestions": suggestions,
        "today": date.today().isoformat(),
    })


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def registration_sheet_pdf(request, group_id):
    group = get_object_or_404(Group, pk=group_id)

    students = (
        Enrollment.objects.filter(group=group, is_active=True)
        .select_related("user")
        .order_by("user__name")
    )
    student_names = [e.user.name if hasattr(e.user, "name") and e.user.name else e.user.email for e in students]

    if not student_names:
        return HttpResponse(
            '<div class="alert alert-warning">No hay alumnos matriculados en este grupo.</div>',
            status=200,
        )

    pdf_bytes = generate_registration_sheet(
        student_names,
        title=f"Hoja de Registro — {group.name}",
    )

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    safe_name = group.name.replace(" ", "_")[:30]
    response["Content-Disposition"] = f'attachment; filename="registro_{safe_name}.pdf"'
    return response


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def add_pickup(request, group_id):
    group = get_object_or_404(Group, pk=group_id)

    student_id = request.POST.get("student_id")
    code = request.POST.get("code", "").strip().upper()
    pickup_date = request.POST.get("date", date.today().isoformat())

    if not student_id or not code:
        return HttpResponse(
            '<div class="alert alert-error text-sm" id="pickup-message">'
            'Selecciona un alumno e introduce un código.</div>',
            status=200,
        )

    # Verify student is enrolled in this group
    enrollment = Enrollment.objects.filter(
        group=group, user_id=student_id, is_active=True
    ).select_related("user").first()
    if not enrollment:
        return HttpResponse(
            '<div class="alert alert-error text-sm" id="pickup-message">'
            'Alumno no encontrado en este grupo.</div>',
            status=200,
        )

    # Find or create the StudyCardItem for this code
    item, error = _find_item_by_code(code, group)
    if error:
        return HttpResponse(
            f'<div class="alert alert-error text-sm" id="pickup-message">{error}</div>',
            status=200,
        )

    # Update auto-batch created_by to current user
    if item.batch.created_by_id == 1 and item.batch.created_by_id != request.user.pk:
        item.batch.created_by = request.user
        item.batch.save(update_fields=["created_by"])

    # Check for duplicate
    if StudyCardPickup.objects.filter(card_item=item, student=enrollment.user).exists():
        return HttpResponse(
            f'<div class="alert alert-warning text-sm" id="pickup-message">'
            f'{enrollment.user.name} ya tiene registrada la tarjeta {code}.</div>',
            status=200,
        )

    pickup = StudyCardPickup.objects.create(
        card_item=item,
        student=enrollment.user,
        picked_up_at=pickup_date,
        source="manual",
    )

    return render(request, "clases/study_cards/partials/pickup_row.html", {
        "pickup": pickup,
        "is_new": True,
    })


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def delete_pickup(request, pickup_id):
    pickup = get_object_or_404(StudyCardPickup, pk=pickup_id)
    pickup.delete()
    return HttpResponse("")


# =============================================================================
# OCR UPLOAD
# =============================================================================


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/heic": "image/heic",
}


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def ocr_upload(request, group_id):
    """Upload a registration sheet photo → OCR → return confirmation table."""
    group = get_object_or_404(Group, pk=group_id)

    photo = request.FILES.get("photo")
    if not photo:
        return HttpResponse(
            '<div class="alert alert-error text-sm">No se ha subido ninguna imagen.</div>'
        )

    mime_type = ALLOWED_IMAGE_TYPES.get(photo.content_type)
    if not mime_type:
        return HttpResponse(
            '<div class="alert alert-error text-sm">Formato no soportado. Usa JPEG, PNG o WebP.</div>'
        )

    # Get student names for context
    students = (
        Enrollment.objects.filter(group=group, is_active=True)
        .select_related("user")
        .order_by("user__name")
    )
    student_names = [
        e.user.name if hasattr(e.user, "name") and e.user.name else e.user.email
        for e in students
    ]

    # Build student lookup: name → user_id
    student_lookup = {}
    for e in students:
        name = e.user.name if hasattr(e.user, "name") and e.user.name else e.user.email
        student_lookup[name.lower()] = e.user

    image_bytes = photo.read()
    results, error = ocr_registration_sheet(image_bytes, mime_type, student_names)

    if error:
        return HttpResponse(
            f'<div class="alert alert-error text-sm">{error}</div>'
        )

    if not results:
        return HttpResponse(
            '<div class="alert alert-warning text-sm">No se detectaron códigos en la imagen.</div>'
        )

    # Match OCR student names to enrolled students
    matched_results = []
    for entry in results:
        ocr_name = entry["student_name"]
        # Fuzzy match: try exact, then case-insensitive, then partial
        user = student_lookup.get(ocr_name.lower())
        if not user:
            # Try partial match
            for key, u in student_lookup.items():
                if ocr_name.lower() in key or key in ocr_name.lower():
                    user = u
                    break

        if user and entry["codes"]:
            matched_results.append({
                "student_name": user.name if hasattr(user, "name") and user.name else user.email,
                "student_id": user.pk,
                "codes": entry["codes"],
                "confidence": entry["confidence"],
            })

    if not matched_results:
        return HttpResponse(
            '<div class="alert alert-warning text-sm">Se detectaron códigos pero no se pudieron asociar a alumnos matriculados.</div>'
        )

    return render(request, "clases/study_cards/partials/ocr_confirmation.html", {
        "results": matched_results,
        "group": group,
        "today": date.today().isoformat(),
    })


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def ocr_confirm(request, group_id):
    """Confirm OCR results and batch-create pickups."""
    group = get_object_or_404(Group, pk=group_id)
    pickup_date = request.POST.get("date", date.today().isoformat())

    # Parse confirmed entries from form: entries like "entry_0_student_id", "entry_0_code_0"
    entries = {}
    for key, value in request.POST.items():
        if key.startswith("entry_") and "_student_id" in key:
            idx = key.split("_")[1]
            entries[idx] = {"student_id": value, "codes": []}
        elif key.startswith("code_"):
            # code_0_1 = entry 0, code 1 (if checked)
            parts = key.split("_")
            if len(parts) == 3:
                idx, _ = parts[1], parts[2]
                if idx in entries:
                    entries[idx]["codes"].append(value)

    created = 0
    errors = []

    for idx, entry in entries.items():
        student_id = entry["student_id"]
        enrollment = Enrollment.objects.filter(
            group=group, user_id=student_id, is_active=True
        ).select_related("user").first()
        if not enrollment:
            continue

        for code in entry["codes"]:
            code = code.strip().upper()
            item, err = _find_item_by_code(code, group)
            if err:
                errors.append(f"{code}: {err}")
                continue

            if item.batch.created_by_id == 1:
                item.batch.created_by = request.user
                item.batch.save(update_fields=["created_by"])

            if not StudyCardPickup.objects.filter(card_item=item, student=enrollment.user).exists():
                StudyCardPickup.objects.create(
                    card_item=item,
                    student=enrollment.user,
                    picked_up_at=pickup_date,
                    source="photo_ocr",
                )
                created += 1

    msg = f'<div class="alert alert-success text-sm">{created} recogida{"s" if created != 1 else ""} registrada{"s" if created != 1 else ""} desde OCR.</div>'
    if errors:
        msg += f'<div class="alert alert-warning text-sm mt-2">Errores: {"; ".join(errors)}</div>'

    return HttpResponse(msg)
