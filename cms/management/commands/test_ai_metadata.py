"""
Django management command to test AI metadata extraction.

This command helps diagnose issues with the Gemini API in production
by testing metadata extraction with sample input.

Usage:
    python manage.py test_ai_metadata
    python manage.py test_ai_metadata --description "Partitura de piano de Extremoduro - So Payaso"
"""

from django.core.management.base import BaseCommand
from django.conf import settings

from cms.services.ai_metadata_extractor import AIMetadataExtractor


class Command(BaseCommand):
    help = "Test AI metadata extraction to diagnose production issues"

    def add_arguments(self, parser):
        parser.add_argument(
            "--description",
            type=str,
            default="Partitura para piano de Extremoduro - So Payaso",
            help="Description to test with (default: sample piano score)",
        )
        parser.add_argument(
            "--files",
            type=str,
            nargs="+",
            default=["PDF: so_payaso_piano.pdf"],
            help="File names to include in test (default: sample PDF)",
        )

    def handle(self, *args, **options):
        description = options["description"]
        file_names = options["files"]

        self.stdout.write(self.style.NOTICE("=" * 70))
        self.stdout.write(self.style.NOTICE("AI Metadata Extraction Test"))
        self.stdout.write(self.style.NOTICE("=" * 70))

        # Check API key configuration
        self.stdout.write("\n🔍 Checking configuration...")
        if not settings.GEMINI_API_KEY:
            self.stdout.write(
                self.style.ERROR(
                    "❌ GEMINI_API_KEY is not configured in settings!"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "   Please add GEMINI_API_KEY to your .env file."
                )
            )
            return
        else:
            api_key_preview = settings.GEMINI_API_KEY[:10] + "..." + settings.GEMINI_API_KEY[-4:]
            self.stdout.write(
                self.style.SUCCESS(f"✓ GEMINI_API_KEY is configured: {api_key_preview}")
            )

        # Test metadata extraction
        self.stdout.write("\n📋 Test Input:")
        self.stdout.write(f"   Description: {description}")
        self.stdout.write(f"   Files: {', '.join(file_names)}")

        self.stdout.write("\n🤖 Calling Gemini API...")

        try:
            extractor = AIMetadataExtractor()
            metadata = extractor.extract_metadata(description, file_names)

            self.stdout.write(self.style.SUCCESS("\n✓ Metadata extraction successful!"))
            self.stdout.write("\n📊 Extracted Metadata:")
            self.stdout.write("   " + "-" * 66)

            # Display each field
            fields = [
                ("Title", "title"),
                ("Composer", "composer"),
                ("Key Signature", "key_signature"),
                ("Tempo", "tempo"),
                ("Time Signature", "time_signature"),
                ("Difficulty", "difficulty"),
                ("Duration (minutes)", "duration_minutes"),
                ("Reference Catalog", "reference_catalog"),
                ("Description", "description"),
                ("Notes", "notes"),
            ]

            for label, field in fields:
                value = metadata.get(field, "")
                if value:
                    # Truncate long values
                    display_value = str(value)
                    if len(display_value) > 60:
                        display_value = display_value[:57] + "..."
                    self.stdout.write(f"   {label:20}: {display_value}")

            # Display categories and tags
            categories = metadata.get("categories", [])
            if categories:
                self.stdout.write(f"   Categories          : {', '.join(categories)}")

            tags = metadata.get("tags", [])
            if tags:
                self.stdout.write(f"   Tags                : {', '.join(tags)}")

            # Display file-specific tags
            files = metadata.get("files", [])
            if files:
                self.stdout.write("\n   File-specific tags:")
                for file_meta in files:
                    filename = file_meta.get("filename", "unknown")
                    file_tags = file_meta.get("tags", [])
                    self.stdout.write(f"      {filename}: {', '.join(file_tags)}")

            self.stdout.write("   " + "-" * 66)

            # Check for fallback values (indicating API failure)
            if metadata.get("title") == "Sin título":
                self.stdout.write(
                    self.style.WARNING(
                        "\n⚠️  Warning: Title is 'Sin título' - possible API failure"
                    )
                )
            if not metadata.get("composer"):
                self.stdout.write(
                    self.style.WARNING(
                        "⚠️  Warning: Composer is empty - possible API failure"
                    )
                )

            # Success indicators
            success_count = 0
            if metadata.get("title") and metadata.get("title") != "Sin título":
                success_count += 1
            if metadata.get("composer"):
                success_count += 1
            if metadata.get("categories"):
                success_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Extraction quality: {success_count}/3 key fields populated"
                )
            )

        except ValueError as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Validation error: {str(e)}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Extraction failed: {str(e)}")
            )
            self.stdout.write(
                self.style.WARNING(
                    "\nPossible causes:"
                    "\n   - Gemini API key is invalid"
                    "\n   - Network connectivity issues"
                    "\n   - API rate limiting"
                    "\n   - API service outage"
                )
            )

        self.stdout.write("\n" + "=" * 70 + "\n")
