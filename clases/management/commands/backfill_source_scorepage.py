"""
Backfill source_page for existing ClassSessionItems.

Usage:
  # Dry run (default) - shows what would be set
  python manage.py backfill_source_scorepage

  # Auto-assign items with exactly 1 ScorePage match
  python manage.py backfill_source_scorepage --auto

  # Assign all items in a session to a specific Page
  python manage.py backfill_source_scorepage --session 71 --page 42

  # Only show items for a specific session
  python manage.py backfill_source_scorepage --session 71
"""

from django.core.management.base import BaseCommand
from wagtail.models import Page

from clases.models import ClassSessionItem
from cms.models import ScorePage


def find_all_scorepages(item):
    """Find ALL ScorePages containing this item's resource."""
    if item.content_type.model not in ("document", "image", "embed"):
        return []
    if not item.content_object:
        return []

    def _get_val(block_value, key):
        if hasattr(block_value, "get"):
            return block_value.get(key)
        return getattr(block_value, key, None)

    matches = []
    for score in ScorePage.objects.live().order_by("title"):
        for block in score.content:
            try:
                if block.block_type in ("pdf_score", "audio"):
                    field = "pdf_file" if block.block_type == "pdf_score" else "audio_file"
                    val = _get_val(block.value, field)
                    if val and hasattr(val, "pk") and val.pk == item.content_object.pk:
                        matches.append(score)
                        break
                elif block.block_type == "image":
                    val = _get_val(block.value, "image")
                    if val and hasattr(val, "pk") and val.pk == item.content_object.pk:
                        matches.append(score)
                        break
                elif block.block_type == "embed":
                    val = _get_val(block.value, "url")
                    if (
                        val
                        and hasattr(item.content_object, "url")
                        and val == item.content_object.url
                    ):
                        matches.append(score)
                        break
            except (AttributeError, KeyError, TypeError):
                continue
    return matches


class Command(BaseCommand):
    help = "Backfill source_page for existing ClassSessionItems"

    def add_arguments(self, parser):
        parser.add_argument(
            "--auto",
            action="store_true",
            help="Auto-assign items with exactly 1 ScorePage match",
        )
        parser.add_argument(
            "--session",
            type=int,
            help="Only process items in this session ID",
        )
        parser.add_argument(
            "--page",
            type=int,
            help="Force-assign this Page ID (requires --session)",
        )
        # Keep --scorepage as alias for backwards compat
        parser.add_argument(
            "--scorepage",
            type=int,
            help="Alias for --page",
        )

    def handle(self, *args, **options):
        auto = options["auto"]
        session_id = options["session"]
        page_id = options["page"] or options["scorepage"]

        qs = ClassSessionItem.objects.filter(source_page__isnull=True)
        if session_id:
            qs = qs.filter(session_id=session_id)

        items = list(qs.select_related("content_type", "session"))

        if not items:
            self.stdout.write(self.style.SUCCESS("No items need backfilling."))
            return

        # Bulk assign mode
        if page_id:
            if not session_id:
                self.stderr.write("--page requires --session")
                return
            try:
                page = Page.objects.get(pk=page_id)
            except Page.DoesNotExist:
                self.stderr.write(f"Page pk={page_id} not found")
                return

            count = qs.update(source_page=page)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Assigned {count} items in session {session_id} → {page.title}"
                )
            )
            return

        # Per-item processing
        auto_count = 0
        multi_count = 0
        no_match_count = 0

        for item in items:
            matches = find_all_scorepages(item)
            title = item.get_content_title()
            model = item.content_type.model

            if len(matches) == 0:
                no_match_count += 1
                self.stdout.write(
                    f"  ⚪ pk={item.pk} Session {item.session_id} | "
                    f"{model} | {title} → NO MATCH"
                )
            elif len(matches) == 1:
                if auto:
                    item.source_page = matches[0]
                    item.save(update_fields=["source_page"])
                    auto_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✅ pk={item.pk} Session {item.session_id} | "
                            f"{model} | {title} → {matches[0].title}"
                        )
                    )
                else:
                    self.stdout.write(
                        f"  🟢 pk={item.pk} Session {item.session_id} | "
                        f"{model} | {title} → {matches[0].title} (1 match, use --auto)"
                    )
            else:
                multi_count += 1
                match_list = ", ".join(
                    f"{s.title} (pk={s.pk})" for s in matches
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"  🟡 pk={item.pk} Session {item.session_id} | "
                        f"{model} | {title} → MULTIPLE: {match_list}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(f"Summary: {len(items)} items total")
        if auto:
            self.stdout.write(self.style.SUCCESS(f"  Auto-assigned: {auto_count}"))
        self.stdout.write(f"  Multiple matches (manual): {multi_count}")
        self.stdout.write(f"  No match: {no_match_count}")

        if multi_count > 0:
            self.stdout.write(
                "\nFor items with multiple matches, use:\n"
                "  python manage.py backfill_source_scorepage --session <ID> --page <ID>"
            )
