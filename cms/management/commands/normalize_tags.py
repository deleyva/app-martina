"""
Management command to normalize existing tags case-insensitively.

This script:
1. Finds all tags in the database
2. Groups them by normalized name (lowercase)
3. Merges duplicates (e.g., "Piano" and "piano" become one tag)
4. Updates all references to use the canonical (lowercase) version
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from taggit.models import Tag, TaggedItem
from collections import defaultdict


class Command(BaseCommand):
    help = 'Normalize tags to lowercase and merge case-insensitive duplicates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write("Analyzing tags...")
        
        # Group tags by normalized name
        tag_groups = defaultdict(list)
        for tag in Tag.objects.all():
            normalized = tag.name.lower().strip()
            tag_groups[normalized].append(tag)
        
        # Find duplicates
        duplicates = {k: v for k, v in tag_groups.items() if len(v) > 1}
        
        if not duplicates:
            self.stdout.write(self.style.SUCCESS('No duplicate tags found. All tags are already normalized.'))
            return
        
        self.stdout.write(f"Found {len(duplicates)} groups of duplicate tags:")
        
        with transaction.atomic():
            for normalized_name, duplicate_tags in duplicates.items():
                # Sort by usage count (most used becomes canonical)
                duplicate_tags.sort(
                    key=lambda t: TaggedItem.objects.filter(tag=t).count(),
                    reverse=True
                )
                
                canonical = duplicate_tags[0]
                others = duplicate_tags[1:]
                
                self.stdout.write(f"\n  '{normalized_name}':")
                self.stdout.write(f"    Canonical: '{canonical.name}' ({TaggedItem.objects.filter(tag=canonical).count()} uses)")
                
                for other in others:
                    usage_count = TaggedItem.objects.filter(tag=other).count()
                    self.stdout.write(f"    Duplicate: '{other.name}' ({usage_count} uses)")
                    
                    if not dry_run:
                        # Update all TaggedItems to use canonical tag
                        TaggedItem.objects.filter(tag=other).update(tag=canonical)
                        # Delete the duplicate tag
                        other.delete()
                        self.stdout.write(f"      → Merged into '{canonical.name}'")
            
            if not dry_run:
                # Normalize all remaining tags to lowercase
                self.stdout.write("\nNormalizing all tag names to lowercase...")
                for tag in Tag.objects.all():
                    if tag.name != tag.name.lower().strip():
                        old_name = tag.name
                        tag.name = tag.name.lower().strip()
                        tag.save()
                        self.stdout.write(f"  '{old_name}' → '{tag.name}'")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN COMPLETE - No changes were made'))
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Tag normalization complete'))
