"""
Management command to audit and maintain tags.

Usage:
    python manage.py audit_tags
    python manage.py audit_tags --fix
    python manage.py audit_tags --threshold 0.9
    python manage.py audit_tags --merge "tag1" "tag2"
"""

from difflib import SequenceMatcher

from django.core.management.base import BaseCommand
from django.db import models
from taggit.models import Tag


class Command(BaseCommand):
    help = "Audit tags: find unused, similar (duplicates), and long tags"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Apply automatic fixes (delete unused tags)",
        )
        parser.add_argument(
            "--threshold",
            type=float,
            default=0.85,
            help="Similarity threshold for duplicate detection (0.0-1.0, default: 0.85)",
        )
        parser.add_argument(
            "--merge",
            nargs=2,
            metavar=("SOURCE", "TARGET"),
            help="Merge SOURCE tag into TARGET tag",
        )
        parser.add_argument(
            "--delete",
            type=str,
            help="Delete a specific tag by name",
        )

    def handle(self, *args, **options):
        # Handle specific actions first
        if options["merge"]:
            self._merge_tags(options["merge"][0], options["merge"][1])
            return

        if options["delete"]:
            self._delete_tag(options["delete"])
            return

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.HTTP_INFO("    AUDITORÍA DE TAGS"))
        self.stdout.write("=" * 50 + "\n")

        # 1. Unused tags
        self._check_unused_tags(fix=options["fix"])

        # 2. Long tags
        self._check_long_tags()

        # 3. Similar tags (potential duplicates)
        self._check_similar_tags(threshold=options["threshold"])

        # 4. Statistics
        self._show_statistics()

    def _check_unused_tags(self, fix=False):
        """Find and optionally delete unused tags"""
        unused = Tag.objects.annotate(
            usage_count=models.Count("taggit_taggeditem_items")
        ).filter(usage_count=0)

        if unused.exists():
            self.stdout.write(
                self.style.WARNING(f"\n❌ Tags sin usar ({unused.count()}):")
            )
            for tag in unused:
                self.stdout.write(f"   • {tag.name}")

            if fix:
                count = unused.count()
                unused.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"   → {count} tags eliminados")
                )
            else:
                self.stdout.write(
                    self.style.NOTICE(
                        "   Usa --fix para eliminarlos automáticamente"
                    )
                )
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ No hay tags sin usar"))

    def _check_long_tags(self):
        """Find tags longer than 30 characters"""
        # Using raw query to get length
        long_tags = []
        for tag in Tag.objects.all():
            if len(tag.name) > 30:
                long_tags.append(tag)

        if long_tags:
            self.stdout.write(
                self.style.WARNING(f"\n⚠️ Tags largos (>30 chars) ({len(long_tags)}):")
            )
            for tag in long_tags[:10]:
                self.stdout.write(f'   • "{tag.name}" ({len(tag.name)} chars)')
            if len(long_tags) > 10:
                self.stdout.write(f"   ... y {len(long_tags) - 10} más")
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ No hay tags excesivamente largos"))

    def _check_similar_tags(self, threshold=0.85):
        """Find tags with similar names (potential duplicates)"""
        self.stdout.write("\n🔍 Buscando tags similares...")

        all_tags = list(Tag.objects.values_list("name", flat=True))
        suggestions = []

        for i, tag1 in enumerate(all_tags):
            for tag2 in all_tags[i + 1:]:
                ratio = SequenceMatcher(None, tag1.lower(), tag2.lower()).ratio()
                if ratio >= threshold:
                    suggestions.append((tag1, tag2, ratio))

        if suggestions:
            self.stdout.write(
                self.style.WARNING(f"\n🔀 Posibles duplicados ({len(suggestions)}):")
            )
            for t1, t2, ratio in sorted(suggestions, key=lambda x: -x[2])[:15]:
                self.stdout.write(f'   "{t1}" ↔ "{t2}" ({ratio:.0%} similar)')

            if len(suggestions) > 15:
                self.stdout.write(f"   ... y {len(suggestions) - 15} más")

            self.stdout.write(
                self.style.NOTICE(
                    "\n   Para fusionar: python manage.py audit_tags --merge 'tag1' 'tag2'"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n✓ No se encontraron duplicados (umbral: {threshold:.0%})")
            )

    def _show_statistics(self):
        """Show tag usage statistics"""
        self.stdout.write("\n" + "-" * 40)
        self.stdout.write(self.style.HTTP_INFO("📊 ESTADÍSTICAS"))
        self.stdout.write("-" * 40)

        total_tags = Tag.objects.count()
        self.stdout.write(f"   Total de tags: {total_tags}")

        # Most used tags
        most_used = (
            Tag.objects.annotate(count=models.Count("taggit_taggeditem_items"))
            .order_by("-count")[:5]
        )
        self.stdout.write("\n   Top 5 más usados:")
        for tag in most_used:
            self.stdout.write(f"      • {tag.name}: {tag.count} items")

        # Least used (but not zero)
        least_used = (
            Tag.objects.annotate(count=models.Count("taggit_taggeditem_items"))
            .filter(count__gt=0)
            .order_by("count")[:5]
        )
        self.stdout.write("\n   Top 5 menos usados (con uso):")
        for tag in least_used:
            self.stdout.write(f"      • {tag.name}: {tag.count} items")

        self.stdout.write("\n" + "=" * 50 + "\n")

    def _merge_tags(self, source_name, target_name):
        """Merge source tag into target tag"""
        try:
            source = Tag.objects.get(name=source_name)
        except Tag.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Tag "{source_name}" no encontrado')
            )
            return

        try:
            target = Tag.objects.get(name=target_name)
        except Tag.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Tag "{target_name}" no encontrado')
            )
            return

        # Get all items with source tag
        from taggit.models import TaggedItem

        tagged_items = TaggedItem.objects.filter(tag=source)
        count = tagged_items.count()

        # Update to target tag
        for item in tagged_items:
            # Check if target tag already exists for this item
            existing = TaggedItem.objects.filter(
                tag=target,
                content_type=item.content_type,
                object_id=item.object_id,
            ).exists()

            if not existing:
                item.tag = target
                item.save()
            else:
                item.delete()

        # Delete source tag
        source.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Tag "{source_name}" fusionado en "{target_name}" ({count} items actualizados)'
            )
        )

    def _delete_tag(self, tag_name):
        """Delete a specific tag"""
        try:
            tag = Tag.objects.get(name=tag_name)
        except Tag.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Tag "{tag_name}" no encontrado')
            )
            return

        # Count usage
        from taggit.models import TaggedItem

        count = TaggedItem.objects.filter(tag=tag).count()

        if count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'Tag "{tag_name}" tiene {count} usos. '
                    f"¿Estás seguro? (esto eliminará el tag de todos los items)"
                )
            )
            confirm = input("Escribe 'ELIMINAR' para confirmar: ")
            if confirm != "ELIMINAR":
                self.stdout.write(self.style.NOTICE("Operación cancelada"))
                return

        tag.delete()
        self.stdout.write(
            self.style.SUCCESS(f'✓ Tag "{tag_name}" eliminado')
        )
