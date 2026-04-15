"""
Generate study card PDFs from book images.

Usage:
    python manage.py generate_study_cards --book "Libreta Musical" --chapters 1,2,3 --output /tmp/cards.pdf
    python manage.py generate_study_cards --book "Libreta Musical" --all-chapters --output /tmp/cards.pdf
    python manage.py generate_study_cards --page-id 42 --output /tmp/cards.pdf
"""
from django.core.management.base import BaseCommand, CommandError

from clases.services.card_codes import generate_codes_for_page
from clases.services.card_pdf import generate_cards_pdf
from cms.models import BlogIndexPage, BlogPage


class Command(BaseCommand):
    help = "Generate study card PDFs from book chapter images"

    def add_arguments(self, parser):
        parser.add_argument("--book", type=str, help="Book title (BlogIndexPage)")
        parser.add_argument(
            "--chapters", type=str, help="Comma-separated chapter numbers (1-based)"
        )
        parser.add_argument(
            "--all-chapters", action="store_true", help="Include all chapters"
        )
        parser.add_argument("--page-id", type=int, help="Specific BlogPage ID")
        parser.add_argument(
            "--output", type=str, required=True, help="Output PDF path"
        )
        parser.add_argument(
            "--max-width", type=int, default=800, help="Max image width for renditions"
        )

    def handle(self, *args, **options):
        pages = []

        if options["page_id"]:
            try:
                page = BlogPage.objects.get(pk=options["page_id"])
                pages = [page]
            except BlogPage.DoesNotExist:
                raise CommandError(
                    f"BlogPage with ID {options['page_id']} not found"
                )

        elif options["book"]:
            try:
                book = BlogIndexPage.objects.get(title__icontains=options["book"])
            except BlogIndexPage.DoesNotExist:
                raise CommandError(f"Book '{options['book']}' not found")
            except BlogIndexPage.MultipleObjectsReturned:
                books = BlogIndexPage.objects.filter(
                    title__icontains=options["book"]
                )
                raise CommandError(
                    f"Multiple books match '{options['book']}': "
                    + ", ".join(f"{b.title} (ID: {b.pk})" for b in books)
                )

            chapter_pages = list(
                book.get_children().type(BlogPage).specific().order_by("path")
            )

            if options["all_chapters"]:
                pages = chapter_pages
            elif options["chapters"]:
                chapter_nums = [
                    int(n.strip()) for n in options["chapters"].split(",")
                ]
                for num in chapter_nums:
                    if 1 <= num <= len(chapter_pages):
                        pages.append(chapter_pages[num - 1])
                    else:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Chapter {num} out of range (1-{len(chapter_pages)})"
                            )
                        )
            else:
                raise CommandError(
                    "Specify --chapters or --all-chapters with --book"
                )
        else:
            raise CommandError("Specify either --book or --page-id")

        if not pages:
            raise CommandError("No pages found to process")

        # Get all books for collision detection
        all_books = list(BlogIndexPage.objects.live())

        # Generate codes for all pages
        all_items = []
        for page in pages:
            codes = generate_codes_for_page(page, all_books=all_books)
            all_items.extend(codes)
            self.stdout.write(f"  {page.title}: {len(codes)} images")

        if not all_items:
            raise CommandError("No images found in selected pages")

        self.stdout.write(f"\nGenerating PDF with {len(all_items)} cards...")
        output = generate_cards_pdf(all_items, output_path=options["output"])
        self.stdout.write(self.style.SUCCESS(f"PDF saved to {output}"))
