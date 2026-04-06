"""
Backfill source_page for existing LibraryItems.
Uses the same StreamField search logic as get_related_scorepage() fallback.
"""
from django.core.management.base import BaseCommand

from my_library.models import LibraryItem


class Command(BaseCommand):
    help = "Backfill source_page for existing LibraryItems without one"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        items = LibraryItem.objects.filter(source_page__isnull=True).exclude(
            content_type__model="scorepage"
        )
        total = items.count()
        self.stdout.write(f"Found {total} items without source_page")

        updated = 0
        not_found = 0
        for item in items:
            try:
                score = item._search_scorepage_in_streamfields()
                if score:
                    if dry_run:
                        self.stdout.write(
                            f"  [DRY] {item} -> {score.title}"
                        )
                    else:
                        item.source_page = score
                        item.save(update_fields=["source_page"])
                    updated += 1
                else:
                    not_found += 1
                    self.stdout.write(
                        self.style.WARNING(f"  No ScorePage found for: {item}")
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  Error processing {item}: {e}")
                )

        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Updated: {updated}, Not found: {not_found}, Total: {total}"
            )
        )
