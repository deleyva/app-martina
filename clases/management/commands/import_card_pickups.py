"""
Import study card pickups from JSON (output of OCR tool).

Usage:
    python manage.py import_card_pickups /path/to/pickups.json
    python manage.py import_card_pickups /path/to/pickups.json --group-id 5
    python manage.py import_card_pickups /path/to/pickups.json --dry-run

JSON format:
[
    {
        "student": "Nombre Apellido",
        "codes": ["LM-3-07", "GD-1-02"],
        "date": "2026-04-15",
        "confidence": 0.95
    }
]
"""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from clases.models import Enrollment, StudyCardItem, StudyCardPickup

User = get_user_model()


class Command(BaseCommand):
    help = "Import study card pickups from JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            "json_file", type=str, help="Path to JSON file with pickup data"
        )
        parser.add_argument(
            "--group-id", type=int, help="Group ID to match students against"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without saving",
        )

    def handle(self, *args, **options):
        try:
            with open(options["json_file"], "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise CommandError(f"Error reading JSON file: {e}")

        created_count = 0
        skipped_count = 0
        error_count = 0

        # Batch-fetch all card items by code to avoid N+1 queries
        all_codes = [code for entry in data for code in entry.get("codes", [])]
        card_items_by_code = {
            item.code: item
            for item in StudyCardItem.objects.filter(code__in=all_codes)
        }

        for entry in data:
            student_name = entry.get("student", "")
            codes = entry.get("codes", [])
            pickup_date = entry.get("date", date.today().isoformat())
            confidence = entry.get("confidence")

            # Find student by name
            user = self._find_student(student_name, options.get("group_id"))
            if not user:
                self.stderr.write(
                    self.style.WARNING(f"Student not found: '{student_name}'")
                )
                error_count += len(codes)
                continue

            for code in codes:
                card_item = card_items_by_code.get(code)
                if not card_item:
                    self.stderr.write(
                        self.style.WARNING(f"Card code not found: '{code}'")
                    )
                    error_count += 1
                    continue

                if options["dry_run"]:
                    self.stdout.write(
                        f"  [DRY RUN] {student_name} <- {code} ({pickup_date})"
                    )
                    created_count += 1
                    continue

                _, created = StudyCardPickup.objects.get_or_create(
                    card_item=card_item,
                    student=user,
                    defaults={
                        "picked_up_at": pickup_date,
                        "source": "photo_ocr",
                        "confidence": confidence,
                    },
                )
                if created:
                    created_count += 1
                    self.stdout.write(f"  {student_name} <- {code}")
                else:
                    skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nImported: {created_count} | "
                f"Skipped (duplicate): {skipped_count} | "
                f"Errors: {error_count}"
            )
        )

    def _find_student(self, name, group_id=None):
        """Find a user by name, optionally within a group."""
        if group_id:
            enrollments = Enrollment.objects.filter(
                group_id=group_id,
                is_active=True,
                user__name__icontains=name.strip(),
            ).select_related("user")
            if enrollments.exists():
                return enrollments.first().user

        # Fallback: search all users
        users = User.objects.filter(name__icontains=name.strip())
        if users.count() == 1:
            return users.first()
        return None
