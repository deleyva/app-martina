"""
Migrate CMS data (ScorePage, MusicComposer, MusicCategory) to ContentHub.

Usage:
    python manage.py migrate_cms_to_content_hub --dry-run  # Preview
    python manage.py migrate_cms_to_content_hub            # Execute
    python manage.py migrate_cms_to_content_hub --clear    # Clear and re-migrate
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from content_hub.models import ContentItem, ContentLink, Category, ContentCategoryOrder


class Command(BaseCommand):
    help = "Migrate CMS data (ScorePage, Composers, Categories) to ContentHub"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview migration without making changes",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing ContentHub data before migrating",
        )
        parser.add_argument(
            "--skip-scores",
            action="store_true",
            help="Skip ScorePage migration",
        )
        parser.add_argument(
            "--skip-composers",
            action="store_true",
            help="Skip MusicComposer migration",
        )
        parser.add_argument(
            "--skip-categories",
            action="store_true",
            help="Skip MusicCategory migration",
        )

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.verbosity = options["verbosity"]

        # Import CMS models (may not exist in all environments)
        try:
            from cms.models import MusicComposer, MusicCategory, ScorePage
            self.MusicComposer = MusicComposer
            self.MusicCategory = MusicCategory
            self.ScorePage = ScorePage
        except ImportError as e:
            self.stderr.write(self.style.ERROR(f"Cannot import CMS models: {e}"))
            return

        if self.dry_run:
            self.stdout.write(self.style.WARNING("\n=== DRY RUN MODE ===\n"))

        # Stats tracking
        self.stats = {
            "composers_migrated": 0,
            "categories_migrated": 0,
            "scores_migrated": 0,
            "content_items_created": 0,
            "links_created": 0,
            "errors": [],
        }

        # Mappings for relationships
        self.composer_map = {}  # old_id -> new ContentItem
        self.category_map = {}  # old_id -> new Category

        if options["clear"] and not self.dry_run:
            self._clear_content_hub()

        with transaction.atomic():
            if not options["skip_categories"]:
                self._migrate_categories()

            if not options["skip_composers"]:
                self._migrate_composers()

            if not options["skip_scores"]:
                self._migrate_scores()

            if self.dry_run:
                # Rollback in dry-run mode
                transaction.set_rollback(True)

        self._print_summary()

    def _clear_content_hub(self):
        """Clear all ContentHub data"""
        self.stdout.write(self.style.WARNING("Clearing existing ContentHub data..."))
        ContentLink.objects.all().delete()
        ContentCategoryOrder.objects.all().delete()
        ContentItem.objects.all().delete()
        Category.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("ContentHub cleared."))

    def _migrate_categories(self):
        """Migrate MusicCategory to content_hub.Category"""
        self.stdout.write("\n--- Migrating Categories ---")

        categories = self.MusicCategory.objects.all().order_by("id")
        total = categories.count()
        self.stdout.write(f"Found {total} MusicCategories")

        # Pre-compute unique slugs to handle duplicates in source data
        used_slugs = set()

        # First pass: create all categories without parents
        for cat in categories:
            try:
                # Generate unique slug (handle duplicates by appending source id)
                base_slug = slugify(cat.name) or f"category-{cat.id}"
                slug = base_slug
                if slug in used_slugs:
                    slug = f"{base_slug}-{cat.id}"
                    self.stdout.write(
                        self.style.WARNING(f"  [~] Duplicate slug detected: '{base_slug}' -> '{slug}'")
                    )
                used_slugs.add(slug)

                new_cat = Category(
                    name=cat.name,
                    slug=slug,
                    description="",
                    order=0,
                )
                if not self.dry_run:
                    new_cat.save()
                self.category_map[cat.id] = new_cat
                self.stats["categories_migrated"] += 1

                if self.verbosity >= 2:
                    self.stdout.write(f"  [+] Category: {cat.name} ({slug})")

            except Exception as e:
                self.stats["errors"].append(f"Category {cat.name}: {e}")
                self.stderr.write(self.style.ERROR(f"  [!] Error: {cat.name} - {e}"))

        # Second pass: set parent relationships
        for cat in categories:
            if cat.parent_id and cat.parent_id in self.category_map:
                new_cat = self.category_map.get(cat.id)
                if new_cat:
                    new_cat.parent = self.category_map[cat.parent_id]
                    if not self.dry_run:
                        new_cat.save()

        self.stdout.write(
            self.style.SUCCESS(f"Migrated {self.stats['categories_migrated']} categories")
        )

    def _migrate_composers(self):
        """Migrate MusicComposer to ContentItem(type=author)"""
        self.stdout.write("\n--- Migrating Composers ---")

        composers = self.MusicComposer.objects.all()
        total = composers.count()
        self.stdout.write(f"Found {total} MusicComposers")

        for composer in composers:
            try:
                # Build metadata from composer fields
                metadata = {}
                if composer.birth_year:
                    metadata["birth_year"] = composer.birth_year
                if composer.death_year:
                    metadata["death_year"] = composer.death_year

                item = ContentItem(
                    content_type=ContentItem.ContentType.AUTHOR,
                    title=composer.name,
                    text_content=composer.bio or "",
                    metadata=metadata,
                )
                if not self.dry_run:
                    item.save()

                self.composer_map[composer.id] = item
                self.stats["composers_migrated"] += 1
                self.stats["content_items_created"] += 1

                if self.verbosity >= 2:
                    self.stdout.write(f"  [+] Author: {composer.name}")

            except Exception as e:
                self.stats["errors"].append(f"Composer {composer.name}: {e}")
                self.stderr.write(
                    self.style.ERROR(f"  [!] Error: {composer.name} - {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"Migrated {self.stats['composers_migrated']} composers")
        )

    def _migrate_scores(self):
        """Migrate ScorePage to ContentItem(type=song) with linked content"""
        self.stdout.write("\n--- Migrating ScorePages ---")

        # Get live pages only
        scores = self.ScorePage.objects.live()
        total = scores.count()
        self.stdout.write(f"Found {total} live ScorePages")

        for score in scores:
            try:
                self._migrate_single_score(score)
                self.stats["scores_migrated"] += 1

                if self.verbosity >= 2:
                    self.stdout.write(f"  [+] Score: {score.title}")

            except Exception as e:
                self.stats["errors"].append(f"Score {score.title}: {e}")
                self.stderr.write(
                    self.style.ERROR(f"  [!] Error: {score.title} - {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"Migrated {self.stats['scores_migrated']} scores")
        )

    def _migrate_single_score(self, score):
        """Migrate a single ScorePage with all its content"""
        # Create main song ContentItem
        metadata = {}

        # Extract metadata from score fields if they exist
        if hasattr(score, "key") and score.key:
            metadata["key"] = score.key
        if hasattr(score, "tempo") and score.tempo:
            metadata["tempo"] = score.tempo
        if hasattr(score, "difficulty") and score.difficulty:
            metadata["difficulty"] = score.difficulty

        song_item = ContentItem(
            content_type=ContentItem.ContentType.SONG,
            title=score.title,
            text_content="",
            metadata=metadata,
        )
        if not self.dry_run:
            song_item.save()
        self.stats["content_items_created"] += 1

        # Link to composer if exists
        if score.composer_id and score.composer_id in self.composer_map:
            composer_item = self.composer_map[score.composer_id]
            if not self.dry_run:
                ContentLink.objects.create(
                    source=song_item,
                    target=composer_item,
                    link_type=ContentLink.LinkType.CREATED_BY,
                )
            self.stats["links_created"] += 1

        # Migrate tags
        if hasattr(score, "tags") and score.tags.exists():
            tag_names = list(score.tags.values_list("name", flat=True))
            if not self.dry_run and tag_names:
                song_item.tags.add(*tag_names)

        # Migrate categories
        if hasattr(score, "categories") and score.categories.exists():
            for cms_cat in score.categories.all():
                if cms_cat.id in self.category_map:
                    new_cat = self.category_map[cms_cat.id]
                    if not self.dry_run:
                        ContentCategoryOrder.objects.create(
                            content=song_item,
                            category=new_cat,
                            order=0,
                        )

        # Migrate StreamField content
        if hasattr(score, "content") and score.content:
            self._migrate_streamfield(song_item, score.content)

    def _migrate_streamfield(self, parent_item, stream_content):
        """
        Migrate StreamField blocks to linked ContentItems.

        Common block types in ScorePage:
        - pdf_document: PDF files
        - audio: Audio files
        - image: Images
        - embed: External embeds (YouTube, Hooktheory)
        - richtext: Text content
        """
        for block in stream_content:
            block_type = block.block_type
            block_value = block.value

            try:
                if block_type == "pdf_document":
                    self._create_pdf_item(parent_item, block_value)
                elif block_type == "audio":
                    self._create_audio_item(parent_item, block_value)
                elif block_type == "image":
                    self._create_image_item(parent_item, block_value)
                elif block_type == "embed":
                    self._create_embed_item(parent_item, block_value)
                elif block_type == "video":
                    self._create_video_item(parent_item, block_value)
                elif block_type == "richtext":
                    # Append rich text to parent's text_content
                    if block_value and not self.dry_run:
                        parent_item.text_content += f"\n{block_value}"
                        parent_item.save()
                # Skip other block types or handle as needed

            except Exception as e:
                if self.verbosity >= 2:
                    self.stderr.write(f"    [!] Block {block_type} error: {e}")

    def _create_pdf_item(self, parent_item, block_value):
        """Create ContentItem for PDF and link to parent"""
        # block_value might be a document or have a 'document' key
        doc = block_value.get("document") if isinstance(block_value, dict) else block_value

        if not doc:
            return

        title = getattr(doc, "title", None) or f"PDF - {parent_item.title}"
        file_url = getattr(doc, "url", None) or ""

        item = ContentItem(
            content_type=ContentItem.ContentType.PDF,
            title=title,
            url=file_url,
        )
        if not self.dry_run:
            item.save()
            ContentLink.objects.create(
                source=parent_item,
                target=item,
                link_type=ContentLink.LinkType.CONTAINS,
            )
        self.stats["content_items_created"] += 1
        self.stats["links_created"] += 1

    def _create_audio_item(self, parent_item, block_value):
        """Create ContentItem for audio and link to parent"""
        # Handle different audio block structures
        if isinstance(block_value, dict):
            audio = block_value.get("audio") or block_value.get("file")
            title = block_value.get("title", f"Audio - {parent_item.title}")
        else:
            audio = block_value
            title = f"Audio - {parent_item.title}"

        if not audio:
            return

        file_url = getattr(audio, "url", None) or ""

        item = ContentItem(
            content_type=ContentItem.ContentType.AUDIO,
            title=title,
            url=file_url,
        )
        if not self.dry_run:
            item.save()
            ContentLink.objects.create(
                source=parent_item,
                target=item,
                link_type=ContentLink.LinkType.CONTAINS,
            )
        self.stats["content_items_created"] += 1
        self.stats["links_created"] += 1

    def _create_image_item(self, parent_item, block_value):
        """Create ContentItem for image and link to parent"""
        if isinstance(block_value, dict):
            image = block_value.get("image")
            title = block_value.get("title", f"Image - {parent_item.title}")
        else:
            image = block_value
            title = f"Image - {parent_item.title}"

        if not image:
            return

        file_url = getattr(image, "url", None) or ""

        item = ContentItem(
            content_type=ContentItem.ContentType.IMAGE,
            title=title,
            url=file_url,
        )
        if not self.dry_run:
            item.save()
            ContentLink.objects.create(
                source=parent_item,
                target=item,
                link_type=ContentLink.LinkType.CONTAINS,
            )
        self.stats["content_items_created"] += 1
        self.stats["links_created"] += 1

    def _create_embed_item(self, parent_item, block_value):
        """Create ContentItem for embed and link to parent"""
        if isinstance(block_value, dict):
            url = block_value.get("url", "")
            title = block_value.get("title", f"Embed - {parent_item.title}")
            embed_html = block_value.get("embed_html", "")
        else:
            url = str(block_value) if block_value else ""
            title = f"Embed - {parent_item.title}"
            embed_html = ""

        if not url and not embed_html:
            return

        # Detect provider from URL
        provider = "unknown"
        if "youtube.com" in url or "youtu.be" in url:
            provider = "youtube"
        elif "hooktheory.com" in url:
            provider = "hooktheory"
        elif "soundcloud.com" in url:
            provider = "soundcloud"
        elif "vimeo.com" in url:
            provider = "vimeo"

        item = ContentItem(
            content_type=ContentItem.ContentType.EMBED,
            title=title,
            url=url,
            text_content=embed_html,
            metadata={"provider": provider},
        )
        if not self.dry_run:
            item.save()
            ContentLink.objects.create(
                source=parent_item,
                target=item,
                link_type=ContentLink.LinkType.CONTAINS,
            )
        self.stats["content_items_created"] += 1
        self.stats["links_created"] += 1

    def _create_video_item(self, parent_item, block_value):
        """Create ContentItem for video and link to parent"""
        if isinstance(block_value, dict):
            url = block_value.get("url", "")
            title = block_value.get("title", f"Video - {parent_item.title}")
        else:
            url = str(block_value) if block_value else ""
            title = f"Video - {parent_item.title}"

        if not url:
            return

        item = ContentItem(
            content_type=ContentItem.ContentType.VIDEO,
            title=title,
            url=url,
        )
        if not self.dry_run:
            item.save()
            ContentLink.objects.create(
                source=parent_item,
                target=item,
                link_type=ContentLink.LinkType.CONTAINS,
            )
        self.stats["content_items_created"] += 1
        self.stats["links_created"] += 1

    def _print_summary(self):
        """Print migration summary"""
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("MIGRATION SUMMARY")
        self.stdout.write("=" * 50)

        if self.dry_run:
            self.stdout.write(self.style.WARNING("(DRY RUN - No changes made)"))

        self.stdout.write(f"\nCategories migrated: {self.stats['categories_migrated']}")
        self.stdout.write(f"Composers migrated:  {self.stats['composers_migrated']}")
        self.stdout.write(f"Scores migrated:     {self.stats['scores_migrated']}")
        self.stdout.write(f"ContentItems created: {self.stats['content_items_created']}")
        self.stdout.write(f"Links created:       {self.stats['links_created']}")

        if self.stats["errors"]:
            self.stdout.write(
                self.style.ERROR(f"\nErrors: {len(self.stats['errors'])}")
            )
            for err in self.stats["errors"][:10]:  # Show first 10
                self.stderr.write(f"  - {err}")
            if len(self.stats["errors"]) > 10:
                self.stderr.write(f"  ... and {len(self.stats['errors']) - 10} more")
        else:
            self.stdout.write(self.style.SUCCESS("\nNo errors!"))

        self.stdout.write("=" * 50 + "\n")
