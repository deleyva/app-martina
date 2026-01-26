"""
Management command to update PDF Score block titles in ScorePages.

This script:
1. Finds all ScorePages with PDF Score blocks
2. Updates the title field in each PDF Score block to use the document's title
3. Saves the updated StreamField data
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from cms.models import ScorePage
from wagtail.models import Document


class Command(BaseCommand):
    help = 'Update PDF Score block titles to use document titles'

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
        
        self.stdout.write("Finding ScorePages with PDF Score blocks...")
        
        pages = ScorePage.objects.all()
        updated_count = 0
        block_count = 0
        
        with transaction.atomic():
            for page in pages:
                page_updated = False
                
                # Iterate through StreamField blocks
                for block in page.content:
                    if block.block_type == 'pdf_score':
                        block_count += 1
                        
                        # Get the document
                        pdf_file = block.value.get('pdf_file')
                        if not pdf_file:
                            continue
                        
                        # Get document title
                        if isinstance(pdf_file, Document):
                            doc_title = pdf_file.title
                        else:
                            # It might be an ID
                            try:
                                doc = Document.objects.get(id=pdf_file)
                                doc_title = doc.title
                            except Document.DoesNotExist:
                                self.stdout.write(f"  Warning: Document not found for page '{page.title}'")
                                continue
                        
                        current_title = block.value.get('title', '')
                        
                        # Update if different
                        if current_title != doc_title:
                            self.stdout.write(f"\nPage: {page.title}")
                            self.stdout.write(f"  Current title: '{current_title}'")
                            self.stdout.write(f"  New title:     '{doc_title}'")
                            
                            if not dry_run:
                                # Update the block value
                                block.value['title'] = doc_title
                                page_updated = True
                
                if page_updated and not dry_run:
                    # Save the page
                    page.save_revision().publish()
                    updated_count += 1
                    self.stdout.write(f"  ✓ Updated")
        
        self.stdout.write(f"\n\nProcessed {block_count} PDF Score blocks in {pages.count()} pages")
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\nDRY RUN COMPLETE - Would update {updated_count} pages'))
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✓ Updated {updated_count} pages'))
