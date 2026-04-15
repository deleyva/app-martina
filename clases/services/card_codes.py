"""
Study Card code generator.

Produces deterministic codes from CMS structure:
  {BookAbbrev}-{ChapterNum}-{ImageIdx}

Example: LM-3-07 = Libreta Musical, chapter 3, image 7
"""
from cms.models import BlogPage, BlogIndexPage


def _get_book_abbreviation(index_page):
    """
    Generate abbreviation from BlogIndexPage title (max 3 chars).
    Uses uppercase initials of title words.
    Example: "Libreta Musical" -> "LM", "Guitar for Dummies" -> "GD"
    """
    words = index_page.title.split()
    # Skip common filler words
    skip = {"de", "del", "la", "las", "los", "el", "for", "the", "a", "an", "y", "and"}
    initials = [w[0].upper() for w in words if w.lower() not in skip and len(w) > 0]
    return "".join(initials[:3]) or index_page.title[:2].upper()


def _get_chapter_position(blog_page):
    """
    Get 1-based position of a BlogPage among its siblings, ordered by Wagtail path.
    """
    siblings = (
        blog_page.get_parent()
        .get_children()
        .type(BlogPage)
        .order_by("path")
    )
    for idx, sibling in enumerate(siblings, start=1):
        if sibling.pk == blog_page.pk:
            return idx
    return 1


def find_book_index_page(blog_page):
    """
    Navigate up the Wagtail page tree to find the nearest BlogIndexPage ancestor.
    This is the "book" container.
    """
    ancestors = blog_page.get_ancestors().type(BlogIndexPage).specific()
    if ancestors.exists():
        # Return the closest BlogIndexPage ancestor (last in the list = most specific)
        return ancestors.last()
    # Fallback: use direct parent if it's a BlogIndexPage
    parent = blog_page.get_parent().specific
    if isinstance(parent, BlogIndexPage):
        return parent
    return None


def generate_code(blog_page, image_index, all_books=None):
    """
    Generate a deterministic study card code.

    Args:
        blog_page: A BlogPage instance (the chapter)
        image_index: 1-based index of the image within get_images()
        all_books: Optional list of all BlogIndexPage titles for collision detection

    Returns:
        str: Code like "LM-3-07"
    """
    book = find_book_index_page(blog_page)
    if not book:
        # Fallback: use first 2 chars of page title
        abbrev = blog_page.title[:2].upper()
    else:
        abbrev = _get_book_abbreviation(book)

        # Collision detection: if another book shares the abbreviation
        if all_books is not None:
            same_abbrev = [
                b for b in all_books
                if b.pk != book.pk and _get_book_abbreviation(b) == abbrev
            ]
            if same_abbrev:
                # Add differentiating character from title
                for char in book.title:
                    if char.upper() not in abbrev and char.isalpha():
                        abbrev = abbrev + char.upper()
                        break

    chapter_num = _get_chapter_position(blog_page)
    return f"{abbrev}-{chapter_num}-{image_index:02d}"


def generate_codes_for_page(blog_page, all_books=None):
    """
    Generate codes for all images in a BlogPage.

    Computes book abbreviation and chapter position once, then applies to all images.

    Returns:
        list of (image, code) tuples
    """
    images = blog_page.get_images()
    if not images:
        return []

    # Compute expensive lookups once for the entire page
    book = find_book_index_page(blog_page)
    if not book:
        abbrev = blog_page.title[:2].upper()
    else:
        abbrev = _get_book_abbreviation(book)
        if all_books is not None:
            same_abbrev = [
                b for b in all_books
                if b.pk != book.pk and _get_book_abbreviation(b) == abbrev
            ]
            if same_abbrev:
                for char in book.title:
                    if char.upper() not in abbrev and char.isalpha():
                        abbrev = abbrev + char.upper()
                        break

    chapter_num = _get_chapter_position(blog_page)

    result = []
    for idx, image in enumerate(images, start=1):
        code = f"{abbrev}-{chapter_num}-{idx:02d}"
        result.append((image, code))
    return result
