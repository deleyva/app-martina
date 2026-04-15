"""
Study Card suggestion engine.

Analyzes pickup history and suggests next cards for students.
"""
from collections import defaultdict

from cms.models import BlogPage


def get_suggestions_for_group(group, max_per_student=3):
    """
    For each student in the group with pickups, suggest next sequential images.

    Returns:
        dict: {user: [(image, blog_page, code, reason), ...]}
    """
    from clases.models import Enrollment, StudyCardPickup, StudyCardItem
    from clases.services.card_codes import generate_code, find_book_index_page

    students = Enrollment.objects.filter(group=group, is_active=True).select_related("user")
    suggestions = {}

    for enrollment in students:
        student = enrollment.user
        # Get all pickups for this student in this group's batches
        pickups = (
            StudyCardPickup.objects.filter(
                student=student,
                card_item__batch__group=group,
            )
            .select_related("card_item", "card_item__image", "card_item__source_page")
            .order_by("-picked_up_at")
        )

        if not pickups.exists():
            continue

        student_suggestions = []
        seen_codes = set()

        # Group pickups by book (source_page's parent BlogIndexPage)
        book_pickups = defaultdict(list)
        for pickup in pickups:
            source_page = pickup.card_item.source_page
            if source_page:
                page = source_page.specific
                book = find_book_index_page(page)
                if book:
                    book_pickups[book.pk].append(pickup)

        # For each book, find next sequential images
        for book_pk, book_picks in book_pickups.items():
            if len(student_suggestions) >= max_per_student:
                break

            # Find the latest chapter and image index from pickups
            latest_pickup = book_picks[0]  # Already ordered by -picked_up_at
            source_page = latest_pickup.card_item.source_page.specific
            code_parts = latest_pickup.card_item.code.split("-")

            if len(code_parts) >= 3:
                try:
                    last_img_idx = int(code_parts[-1])
                except ValueError:
                    continue

                # Get all images for this chapter
                images = source_page.get_images()

                # Suggest next images in same chapter
                for next_idx in range(last_img_idx + 1, len(images) + 1):
                    if len(student_suggestions) >= max_per_student:
                        break
                    if next_idx <= len(images):
                        next_code = generate_code(source_page, next_idx)
                        if next_code not in seen_codes:
                            student_suggestions.append({
                                "image": images[next_idx - 1],
                                "source_page": source_page,
                                "code": next_code,
                                "reason": f"Siguiente en {source_page.title}",
                            })
                            seen_codes.add(next_code)

                # If chapter exhausted, suggest next chapter
                if len(student_suggestions) < max_per_student and last_img_idx >= len(images):
                    siblings = (
                        source_page.get_parent()
                        .get_children()
                        .type(BlogPage)
                        .order_by("path")
                    )
                    found_current = False
                    for sibling in siblings:
                        if sibling.pk == source_page.pk:
                            found_current = True
                            continue
                        if found_current:
                            next_page = sibling.specific
                            next_images = next_page.get_images()
                            if next_images:
                                next_code = generate_code(next_page, 1)
                                if next_code not in seen_codes:
                                    student_suggestions.append({
                                        "image": next_images[0],
                                        "source_page": next_page,
                                        "code": next_code,
                                        "reason": f"Siguiente capítulo: {next_page.title}",
                                    })
                                    seen_codes.add(next_code)
                            break

        if student_suggestions:
            suggestions[student] = student_suggestions

    return suggestions
