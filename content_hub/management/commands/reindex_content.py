"""
Management command to reindex all content in Meilisearch.

Usage:
    python manage.py reindex_content
    python manage.py reindex_content --clear
"""

from django.core.management.base import BaseCommand

from content_hub.search import reindex_all, clear_index


class Command(BaseCommand):
    help = "Reindex all ContentItems in Meilisearch"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear the index before reindexing",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing search index...")
            if clear_index():
                self.stdout.write(self.style.SUCCESS("Index cleared"))
            else:
                self.stdout.write(self.style.WARNING("Could not clear index (Meilisearch unavailable?)"))

        self.stdout.write("Reindexing all content...")
        result = reindex_all()

        if "error" in result:
            self.stdout.write(self.style.ERROR(f"Error: {result['error']}"))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Reindex complete:\n"
                f"  - Indexed: {result['indexed']}\n"
                f"  - Failed: {result['failed']}\n"
                f"  - Total: {result['total']}"
            )
        )
