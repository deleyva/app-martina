"""
Management command to import a book chapter or a whole book as Wagtail
BlogPages under a BlogIndexPage ("book") under a MusicLibraryIndexPage.

Two modes:

1. **Single-chapter mode** — pass --manifest (chapter manifest JSON) + the
   chapter metadata args (--chapter-title, --chapter-intro, --images-dir).

2. **Whole-book mode** — pass --book-manifest (book-level manifest JSON)
   + --images-dir pointing at the extraction root. The command iterates
   over every chapter in the manifest, creates a BlogPage for each one,
   and shares the same set of tags across all of them.

Chapter manifest shape:
    [
      {"type": "text",  "text": "paragraph ..."},
      {"type": "heading", "level": 2, "text": "Section"},
      {"type": "image", "file": "ex-01a.jpeg", "caption": "Example 1a"},
      ...
    ]

Book manifest shape:
    {
      "book_title": "Modern Jazz Guitar Concepts — Jens Larsen",
      "chapters": [
        {
          "number": 1,
          "title": "Capítulo 1 — ...",
          "intro": "...",
          "items": [...]   # same shape as chapter manifest
        },
        ...
      ]
    }

Tag handling: pass --tags "tag1,tag2" to apply tags to all created
BlogPages and all their inline Wagtail Images. If --tags is omitted and
the command is running in a TTY, the command prompts interactively once
at the start of the run.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import NoReturn

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from wagtail.images import get_image_model

from cms.models import BlogIndexPage, BlogPage, MusicLibraryIndexPage
from cms.services.content_publisher import ContentPublisher


ImageModel = get_image_model()

# StreamField block name for BlogPage.attachments — defined in cms/models.py:278.
# Keep in sync if the StreamField is renamed.
ATTACHMENT_IMAGE_BLOCK = "image"


class Command(BaseCommand):
    help = (
        "Import a book chapter (BlogPage) with interleaved text and notation "
        "images under a BlogIndexPage (book) under a MusicLibraryIndexPage."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--parent-slug",
            default="indice-de-recursos-musicales",
            help="Slug of the parent MusicLibraryIndexPage.",
        )
        parser.add_argument(
            "--book-title",
            default=None,
            help=(
                'Title of the book (required in single-chapter mode; '
                'taken from book_manifest.book_title in whole-book mode if omitted).'
            ),
        )
        parser.add_argument(
            "--book-intro",
            default="",
            help="Optional intro text for the book BlogIndexPage (used only on create).",
        )
        parser.add_argument(
            "--chapter-title",
            default=None,
            help='Chapter title (single-chapter mode only).',
        )
        parser.add_argument(
            "--chapter-intro",
            default=None,
            help="Short summary for BlogPage.intro (single-chapter mode only).",
        )
        parser.add_argument(
            "--manifest",
            default=None,
            help="Path to a single-chapter manifest JSON (single-chapter mode).",
        )
        parser.add_argument(
            "--book-manifest",
            default=None,
            help=(
                "Path to a whole-book manifest JSON produced by the extractor. "
                "Mutually exclusive with --manifest. Each chapter is imported as a BlogPage."
            ),
        )
        parser.add_argument(
            "--chapter-only",
            type=int,
            default=None,
            help=(
                "With --book-manifest: import only the chapter with this number. "
                "Useful for retrying a single chapter from a larger book."
            ),
        )
        parser.add_argument(
            "--images-dir",
            required=True,
            help=(
                "Directory containing the image files. In single-chapter mode this "
                "holds the files referenced by --manifest. In whole-book mode this "
                "is the extraction root (images referenced as 'ch01/img-001.jpeg' etc.)."
            ),
        )
        parser.add_argument(
            "--tags",
            default=None,
            help=(
                "Comma-separated tags to apply to all created BlogPages and their "
                "inline images. If omitted and running in a TTY, you will be prompted."
            ),
        )
        parser.add_argument(
            "--owner-username",
            default=None,
            help="Username to set as owner of created pages and images. Defaults to first superuser.",
        )
        parser.add_argument(
            "--with-attachment-cards",
            action="store_true",
            help=(
                "Also mirror each image into the BlogPage attachments "
                "StreamField (renders extra 'Resources' cards at the bottom "
                "of the page). Default off — inline embeds already carry "
                "the add-to-library button via get_images()."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without writing to the database.",
        )

    # ------------------------------------------------------------------ utils

    def _abort(self, msg: str) -> NoReturn:
        raise CommandError(msg)

    def _resolve_owner(self, username: str | None):
        User = get_user_model()
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist:
                self._abort(f"No user with username {username!r}.")
        superuser = User.objects.filter(is_superuser=True).order_by("pk").first()
        if not superuser:
            self._abort("No superuser found; pass --owner-username explicitly.")
        return superuser

    def _resolve_parent(self, parent_slug: str) -> MusicLibraryIndexPage:
        try:
            return MusicLibraryIndexPage.objects.get(slug=parent_slug)
        except MusicLibraryIndexPage.DoesNotExist:
            self._abort(f"No MusicLibraryIndexPage with slug {parent_slug!r} found.")

    # ------------------------------------------------------------------ book

    def _find_or_create_book(
        self,
        publisher: ContentPublisher,
        parent: MusicLibraryIndexPage,
        book_title: str,
        book_intro: str,
        dry_run: bool,
    ) -> BlogIndexPage | None:
        existing = (
            BlogIndexPage.objects.child_of(parent)
            .filter(title=book_title)
            .first()
        )
        if existing:
            self.stdout.write(f"Found existing book: {existing.title} (pk={existing.pk})")
            return existing

        self.stdout.write(f"Will create new book: {book_title!r}")
        if dry_run:
            return None

        slug = publisher._generate_unique_slug(book_title, parent)
        book = BlogIndexPage(title=book_title, slug=slug, intro=book_intro or "")
        parent.add_child(instance=book)
        book.save_revision().publish()
        self.stdout.write(
            self.style.SUCCESS(
                f"Created book: {book.title} (pk={book.pk}) at {book.url_path}"
            )
        )
        return book

    # ------------------------------------------------------------- manifest

    def _load_json(self, path: Path):
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._abort(f"File not found: {path}")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            self._abort(f"{path} is not valid JSON: {e}")

    def _validate_items(self, items: list[dict], context: str) -> None:
        if not isinstance(items, list):
            self._abort(f"{context}: items must be a JSON list.")
        for i, item in enumerate(items):
            if not isinstance(item, dict) or item.get("type") not in (
                "text",
                "heading",
                "image",
            ):
                self._abort(f"{context}: item {i} missing type or wrong shape: {item!r}")
            if item["type"] == "image" and "file" not in item:
                self._abort(f"{context}: image item {i} missing 'file' key: {item!r}")
            if item["type"] == "heading" and "text" not in item:
                self._abort(f"{context}: heading item {i} missing 'text' key: {item!r}")

    def _load_manifest(self, manifest_path: Path) -> list[dict]:
        data = self._load_json(manifest_path)
        self._validate_items(data, f"manifest {manifest_path}")
        return data

    def _load_book_manifest(self, manifest_path: Path) -> dict:
        data = self._load_json(manifest_path)
        if not isinstance(data, dict):
            self._abort(f"{manifest_path}: book manifest must be a JSON object.")
        if "chapters" not in data or not isinstance(data["chapters"], list):
            self._abort(f"{manifest_path}: book manifest must contain a 'chapters' list.")
        if not data["chapters"]:
            self._abort(f"{manifest_path}: book manifest has no chapters.")
        for i, ch in enumerate(data["chapters"]):
            if not isinstance(ch, dict):
                self._abort(f"{manifest_path}: chapter {i} is not an object.")
            required = {"number", "title", "items"}
            missing = required - set(ch)
            if missing:
                self._abort(f"{manifest_path}: chapter {i} missing keys {missing}.")
            self._validate_items(ch["items"], f"chapter {ch.get('number', i)}")
        return data

    # ------------------------------------------------------------ tag prompt

    def _prompt_tags_if_needed(self, tags_arg: str | None) -> list[str]:
        """Return a cleaned list of tags.

        If --tags was passed, parse it. If not and stdin is a TTY, prompt
        the user once. Otherwise return an empty list.
        """
        if tags_arg is not None:
            return self._parse_tags(tags_arg)
        if not sys.stdin.isatty():
            return []
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Tag questionnaire"))
        self.stdout.write(
            "Enter tags to apply to every BlogPage and every inline image in this run."
        )
        self.stdout.write("Separate with commas. Press Enter to skip.")
        raw = input("Tags: ").strip()
        return self._parse_tags(raw)

    @staticmethod
    def _parse_tags(raw: str | None) -> list[str]:
        if not raw:
            return []
        seen: set[str] = set()
        out: list[str] = []
        for part in raw.split(","):
            clean = part.strip()
            if clean and clean.lower() not in seen:
                out.append(clean)
                seen.add(clean.lower())
        return out

    # ----------------------------------------------------------- image creation

    def _create_images(
        self,
        publisher: ContentPublisher,
        manifest: list[dict],
        images_dir: Path,
        chapter_title: str,
        tags: list[str] | None = None,
    ) -> dict[str, "ImageModel"]:
        """Create one Wagtail Image per unique file in the manifest.

        Called BEFORE the atomic block so failures in chapter creation can
        cleanly compensate by deleting these Images (see _cleanup_images).
        """
        # Dedupe by filename (manifest may reference the same image twice)
        unique_files: list[str] = []
        seen: set[str] = set()
        for item in manifest:
            if item["type"] != "image":
                continue
            fn = item["file"]
            if fn in seen:
                continue
            seen.add(fn)
            unique_files.append(fn)

        created: dict[str, ImageModel] = {}
        for fn in unique_files:
            path = images_dir / fn
            if not path.exists():
                self._abort(f"Image file missing: {path}")
            # Build a one-line title: use caption if available, else filename
            caption = next(
                (
                    it.get("caption", "")
                    for it in manifest
                    if it["type"] == "image" and it["file"] == fn
                ),
                "",
            )
            title = caption or f"{chapter_title} — {Path(fn).name}"
            with path.open("rb") as f:
                django_file = File(f, name=path.name)
                image = publisher._create_wagtail_image(
                    django_file, title=title, tags=tags or None
                )
            created[fn] = image
        return created

    def _cleanup_images(self, images: dict[str, "ImageModel"]) -> None:
        """Delete images created before a failed atomic block."""
        for fn, image in images.items():
            try:
                if image.file:
                    image.file.delete(save=False)
                image.delete()
            except Exception as e:  # noqa: BLE001 — best-effort cleanup
                self.stdout.write(
                    self.style.WARNING(f"  failed to cleanup Image {fn}: {e}")
                )

    # --------------------------------------------------------------- body

    def _build_body_html(
        self,
        manifest: list[dict],
        images: dict[str, "ImageModel"],
    ) -> str:
        """Build RichText HTML interleaving text paragraphs and image embeds.

        Text is HTML-escaped (source is plain extracted PDF text, no markdown).
        Images become Wagtail `<embed embedtype="image" ...>` tags which are
        rendered into `<img>` on page render.
        """
        parts: list[str] = []
        for item in manifest:
            if item["type"] == "text":
                text = item["text"].strip()
                if not text:
                    continue
                for paragraph in text.split("\n\n"):
                    p = paragraph.strip()
                    if p:
                        parts.append(f"<p>{html.escape(p)}</p>")
                continue

            if item["type"] == "heading":
                level = int(item.get("level", 2))
                level = max(2, min(level, 4))  # clamp to h2..h4
                text = item["text"].strip()
                if text:
                    parts.append(f"<h{level}>{html.escape(text)}</h{level}>")
                continue

            # image
            image = images.get(item["file"])
            if image is None:
                # Should never happen — _create_images ran first
                continue
            caption = item.get("caption", "")
            alt = html.escape(caption or image.title)
            parts.append(
                f'<embed embedtype="image" id="{image.pk}" alt="{alt}" format="fullwidth"/>'
            )
            if caption:
                parts.append(f"<p><em>{html.escape(caption)}</em></p>")
        return "\n".join(parts)

    # ---------------------------------------------------------- attachments

    def _build_attachment_blocks(
        self,
        manifest: list[dict],
        images: dict[str, "ImageModel"],
    ) -> list[tuple[str, dict]]:
        """Return StreamField attachment blocks for every image reference in manifest order."""
        blocks: list[tuple[str, dict]] = []
        idx = 0
        for item in manifest:
            if item["type"] != "image":
                continue
            image = images.get(item["file"])
            if image is None:
                continue
            idx += 1
            caption = item.get("caption", "")
            block_title = caption or f"Pentagrama {idx:02d}"
            blocks.append(
                (
                    ATTACHMENT_IMAGE_BLOCK,
                    {
                        "title": block_title,
                        "image": image,
                        "caption": caption,
                    },
                )
            )
        return blocks

    # ------------------------------------------------------------ per chapter

    def _import_single_chapter(
        self,
        publisher: ContentPublisher,
        book: BlogIndexPage,
        owner,
        *,
        chapter_title: str,
        chapter_intro: str,
        items: list[dict],
        images_dir: Path,
        tags: list[str],
        with_attachment_cards: bool,
    ) -> "BlogPage":
        """Create one BlogPage + its Images. Caller handles the book lookup.

        Creates Images OUTSIDE any atomic block and compensates on failure
        so a failed chapter never leaves orphan files behind.
        """
        chapter_slug = slugify(chapter_title) or "capitulo"

        if BlogPage.objects.child_of(book).filter(slug=chapter_slug).exists():
            self._abort(
                f"BlogPage with slug {chapter_slug!r} already exists under "
                f"{book.title!r}. Aborting."
            )

        self.stdout.write(f"  Creating {len(items)} items...")
        images = self._create_images(
            publisher, items, images_dir, chapter_title, tags=tags
        )
        self.stdout.write(f"  Created {len(images)} Wagtail Images")

        try:
            with transaction.atomic():
                body_html = self._build_body_html(items, images)
                attachments = (
                    self._build_attachment_blocks(items, images)
                    if with_attachment_cards
                    else []
                )

                blog_page = BlogPage(
                    title=chapter_title,
                    slug=chapter_slug,
                    date=timezone.now().date(),
                    intro=chapter_intro[:250],
                    body=body_html,
                    attachments=attachments,
                    owner=owner,
                    featured_image=next(iter(images.values()), None),
                )
                book.add_child(instance=blog_page)

                # Apply tags to the BlogPage
                if tags:
                    tag_objects = [publisher._get_or_create_tag(t) for t in tags]
                    blog_page.tags.set(tag_objects)

                blog_page.save_revision().publish()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ BlogPage pk={blog_page.pk} {blog_page.title!r}"
                    )
                )
                return blog_page
        except Exception:
            self.stdout.write(
                self.style.ERROR("  ✗ Chapter creation failed — cleaning up Images")
            )
            self._cleanup_images(images)
            raise

    # -------------------------------------------------------------------- main

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        parent_slug: str = options["parent_slug"]
        book_title_arg: str | None = options["book_title"]
        book_intro: str = options["book_intro"]
        manifest_path_arg: str | None = options["manifest"]
        book_manifest_path_arg: str | None = options["book_manifest"]
        chapter_only: int | None = options["chapter_only"]
        images_dir = Path(options["images_dir"])
        owner_username: str | None = options["owner_username"]
        with_attachment_cards: bool = options["with_attachment_cards"]
        tags_arg: str | None = options["tags"]

        # --- mode dispatch -------------------------------------------------
        if manifest_path_arg and book_manifest_path_arg:
            self._abort("Pass either --manifest or --book-manifest, not both.")
        if not manifest_path_arg and not book_manifest_path_arg:
            self._abort("One of --manifest or --book-manifest is required.")

        if not images_dir.is_dir():
            self._abort(f"--images-dir not a directory: {images_dir}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE — no database changes"))

        owner = self._resolve_owner(owner_username)
        self.stdout.write(f"Owner: {owner.username or owner.email} (pk={owner.pk})")

        publisher = ContentPublisher(user=owner)

        parent = self._resolve_parent(parent_slug)
        self.stdout.write(
            f"Parent: {parent.title} (pk={parent.pk}, url_path={parent.url_path})"
        )

        # --- gather chapter specs ------------------------------------------
        chapter_specs: list[dict] = []
        if book_manifest_path_arg:
            book_manifest = self._load_book_manifest(Path(book_manifest_path_arg))
            effective_book_title = (
                book_title_arg
                or book_manifest.get("book_title")
                or self._abort("Book title missing in manifest and --book-title not passed.")
            )
            for ch in book_manifest["chapters"]:
                if chapter_only is not None and ch["number"] != chapter_only:
                    continue
                chapter_specs.append(
                    {
                        "number": ch["number"],
                        "title": ch["title"],
                        "intro": ch.get("intro", "") or "",
                        "items": ch["items"],
                    }
                )
            if chapter_only is not None and not chapter_specs:
                self._abort(f"No chapter with number {chapter_only} in the book manifest.")
        else:
            # single-chapter mode
            if not options["chapter_title"]:
                self._abort("--chapter-title required in single-chapter mode.")
            if options["chapter_intro"] is None:
                self._abort("--chapter-intro required in single-chapter mode.")
            if not book_title_arg:
                self._abort("--book-title required in single-chapter mode.")
            effective_book_title = book_title_arg
            items = self._load_manifest(Path(manifest_path_arg))
            chapter_specs.append(
                {
                    "number": 1,
                    "title": options["chapter_title"],
                    "intro": options["chapter_intro"],
                    "items": items,
                }
            )

        total_images = sum(
            1 for spec in chapter_specs for it in spec["items"] if it["type"] == "image"
        )
        total_text = sum(
            1 for spec in chapter_specs for it in spec["items"] if it["type"] == "text"
        )
        total_headings = sum(
            1 for spec in chapter_specs for it in spec["items"] if it["type"] == "heading"
        )
        self.stdout.write(
            f"Plan: {len(chapter_specs)} chapter(s), "
            f"{total_text} text, {total_headings} headings, {total_images} images"
        )

        # --- tag questionnaire --------------------------------------------
        tags = self._prompt_tags_if_needed(tags_arg)
        if tags:
            self.stdout.write(self.style.NOTICE(f"Tags to apply: {', '.join(tags)}"))
        else:
            self.stdout.write("No tags will be applied.")

        if dry_run:
            for spec in chapter_specs:
                self.stdout.write(f"Chapter {spec['number']}: {spec['title']!r}")
                self.stdout.write(f"  intro: {spec['intro'][:80]!r}")
                n_imgs = sum(1 for it in spec["items"] if it["type"] == "image")
                n_txt = sum(1 for it in spec["items"] if it["type"] == "text")
                n_hdr = sum(1 for it in spec["items"] if it["type"] == "heading")
                self.stdout.write(f"  {n_txt} text, {n_hdr} headings, {n_imgs} images")
            self.stdout.write(self.style.WARNING("DRY RUN COMPLETE — no changes persisted."))
            return

        # --- find-or-create the book ---------------------------------------
        book = self._find_or_create_book(
            publisher, parent, effective_book_title, book_intro, dry_run=False
        )
        assert book is not None

        # --- import each chapter ------------------------------------------
        created_pages: list[BlogPage] = []
        for spec in chapter_specs:
            self.stdout.write("")
            self.stdout.write(
                self.style.NOTICE(
                    f"=== Chapter {spec['number']}: {spec['title']} ==="
                )
            )
            page = self._import_single_chapter(
                publisher,
                book,
                owner,
                chapter_title=spec["title"],
                chapter_intro=spec["intro"],
                items=spec["items"],
                images_dir=images_dir,
                tags=tags,
                with_attachment_cards=with_attachment_cards,
            )
            created_pages.append(page)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Import finished: {len(created_pages)} BlogPage(s) created under "
                f"{book.title!r} (pk={book.pk})"
            )
        )
        if tags:
            self.stdout.write(
                self.style.SUCCESS(f"Tags applied: {', '.join(tags)}")
            )
