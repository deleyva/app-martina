"""
List available images per book and chapter.

Usage:
    python manage.py list_book_images
    python manage.py list_book_images --book "Libreta Musical"
    python manage.py list_book_images --book "Libreta Musical" --codes
"""
from django.core.management.base import BaseCommand

from clases.services.card_codes import generate_codes_for_page
from cms.models import BlogIndexPage, BlogPage


class Command(BaseCommand):
    help = "List available images per book and chapter for study cards"

    def add_arguments(self, parser):
        parser.add_argument("--book", type=str, help="Filter by book title")
        parser.add_argument(
            "--codes",
            action="store_true",
            help="Show generated codes for each image",
        )

    def handle(self, *args, **options):
        books = BlogIndexPage.objects.live()

        if options["book"]:
            books = books.filter(title__icontains=options["book"])

        if not books.exists():
            self.stdout.write(self.style.WARNING("No books found"))
            return

        all_books = list(BlogIndexPage.objects.live())

        for book in books:
            chapters = list(
                book.get_children().type(BlogPage).specific().order_by("path")
            )

            if not chapters:
                continue

            total_images = 0
            self.stdout.write(self.style.SUCCESS(f"\n{'=' * 60}"))
            self.stdout.write(self.style.SUCCESS(f"  {book.title} (ID: {book.pk})"))
            self.stdout.write(self.style.SUCCESS(f"{'=' * 60}"))

            for ch_idx, chapter in enumerate(chapters, start=1):
                if options["codes"]:
                    codes = generate_codes_for_page(chapter, all_books=all_books)
                    if not codes:
                        continue
                    total_images += len(codes)
                    self.stdout.write(
                        f"\n  Chapter {ch_idx}: {chapter.title} ({len(codes)} images)"
                    )
                    for img, code in codes:
                        self.stdout.write(f"    {code} - {img.title}")
                else:
                    images = chapter.get_images()
                    if not images:
                        continue
                    total_images += len(images)
                    self.stdout.write(
                        f"\n  Chapter {ch_idx}: {chapter.title} ({len(images)} images)"
                    )

            self.stdout.write(
                f"\n  Total: {total_images} images in {len(chapters)} chapters\n"
            )
