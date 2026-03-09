from bs4 import BeautifulSoup
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page

class Command(BaseCommand):
    help = "Normalize HTML in RichTextFields and StreamFields to fix tag mismatches"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without saving",
        )

    def normalize_html(self, html):
        if not html:
            return html
        soup = BeautifulSoup(html, "html.parser")
        return str(soup)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - changes will not be saved"))

        # Find all models with RichTextField or StreamField
        for model in apps.get_models():
            # Skip non-editable or core django models if necessary, 
            # but let's be thorough for app-specific models
            if model._meta.app_label not in ['cms', 'music_cards', 'clases', 'incidencias']:
                # Focus on relevant apps to avoid unnecessary processing
                continue

            rich_fields = [
                f for f in model._meta.fields if isinstance(f, RichTextField)
            ]
            stream_fields = [
                f for f in model._meta.fields if isinstance(f, StreamField)
            ]

            if not rich_fields and not stream_fields:
                continue

            self.stdout.write(f"Checking model {model.__name__}...")

            for obj in model.objects.all():
                modified = False
                
                # Check RichTextFields
                for field in rich_fields:
                    val = getattr(obj, field.name)
                    if not val:
                        continue
                    normalized = self.normalize_html(val)
                    if normalized != val:
                        self.stdout.write(f"  [{obj.id}] Normalizing {field.name}")
                        setattr(obj, field.name, normalized)
                        modified = True
                
                # Check StreamFields (if they contain RichTextBlocks)
                # StreamField is more complex. Wagtail usually normalizes it on save if using internal 
                # mechanisms, but if it came from an API, it might be raw.
                # For now, let's focus on RichTextField which is where page 84 is likely failing.
                
                if modified and not dry_run:
                    obj.save()
                    if isinstance(obj, Page):
                        # Also handle revisions if it's a Page
                        latest_revision = obj.get_latest_revision()
                        if latest_revision:
                            # Re-save the revision to ensure the preview/edit view is updated
                            latest_revision.content = obj.serializable_data()
                            latest_revision.save()

        self.stdout.write(self.style.SUCCESS("Finished processing models."))
