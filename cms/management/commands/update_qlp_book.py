"""
Update Quick Lessons Pro chapters with embedded videos and PDF/GP attachments.

Expects:
- Videos at: media/videos/quick-lessons-pro/lesson_XX.webm
- PDFs at: /backups/book_extraction/quick-lessons-pro/gp_files/QLP-all-supplementary-files/PDFs/
- GP files at: /backups/book_extraction/quick-lessons-pro/gp_files/QLP-all-supplementary-files/Guitar Pro Files/
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from wagtail.documents.models import Document

from cms.models import BlogIndexPage, BlogPage


# Manifest chapter numbers 1-24 map to video lesson_01-24.
# Chapters 25-29 map to lesson_26-30 (site skips lesson/25/).
CHAPTER_TO_LESSON = {}
for i in range(1, 25):
    CHAPTER_TO_LESSON[i] = i
for i, lesson in enumerate(range(26, 31), start=25):
    CHAPTER_TO_LESSON[i] = lesson


def normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = t.replace(" | ", " ").replace("|", " ")
    t = t.replace(" - ", " ").replace("-", " ")
    t = t.replace("'s", "s").replace("\u2019s", "s")
    t = re.sub(r"\s+", " ", t)
    return t


def find_matching_file(title: str, directory: Path, extension: str) -> Path | None:
    if not directory.exists():
        return None
    norm_title = normalize_title(title)
    best_match = None
    best_score = 0
    for f in directory.iterdir():
        if not f.name.endswith(extension):
            continue
        norm_name = normalize_title(f.stem)
        title_words = set(norm_title.split())
        name_words = set(norm_name.split())
        overlap = len(title_words & name_words)
        total = max(len(title_words), len(name_words))
        score = overlap / total if total else 0
        if score > best_score:
            best_score = score
            best_match = f
    return best_match if best_score >= 0.5 else None


def strip_redundant_lines(body_html: str) -> str:
    """Remove 'Guitar Pro file:' and 'Video available at:' lines from body."""
    # Remove the video tag if already present from previous run
    body_html = re.sub(
        r'<div style="position:relative.*?</video></div>\s*',
        '',
        body_html,
        flags=re.DOTALL,
    )
    # Remove redundant text paragraphs
    body_html = re.sub(r'<p>Guitar Pro file:.*?</p>\s*', '', body_html)
    body_html = re.sub(r'<p>Video available at:.*?</p>\s*', '', body_html)
    return body_html.strip()


def get_or_create_doc(title: str, file_path: Path | None = None,
                      media_relative: str | None = None, stdout=None) -> Document | None:
    """Get existing or create new Document. Supports file upload or media-relative path."""
    existing = Document.objects.filter(title=title).first()
    if existing:
        if stdout:
            stdout.write(f"       Doc exists: {title} (pk={existing.pk})")
        return existing

    doc = Document(title=title)
    if media_relative:
        # Point to existing file in media dir without copying
        doc.file.name = media_relative
        # Calculate file_size from actual file on disk
        from django.conf import settings
        full_path = Path(settings.MEDIA_ROOT) / media_relative
        if full_path.exists():
            doc.file_size = full_path.stat().st_size
        doc.save()
    elif file_path and file_path.exists():
        with file_path.open("rb") as f:
            doc.file.save(file_path.name, File(f), save=True)
    else:
        return None

    if stdout:
        from django.utils.termcolors import colorize
        stdout.write(f"       Created doc: {title} (pk={doc.pk})")
    return doc


class Command(BaseCommand):
    help = "Update Quick Lessons Pro chapters with video embeds and PDF/GP attachments."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        book = BlogIndexPage.objects.filter(title__icontains="Quick Lessons Pro").first()
        if not book:
            self.stderr.write("Book 'Quick Lessons Pro' not found.")
            return

        self.stdout.write(f"Book: {book.title} (pk={book.pk})")
        pages = list(BlogPage.objects.child_of(book).order_by("path"))
        self.stdout.write(f"Found {len(pages)} chapters")

        pdf_dir = Path("/backups/book_extraction/quick-lessons-pro/gp_files/QLP-all-supplementary-files/PDFs")
        gp_dir = Path("/backups/book_extraction/quick-lessons-pro/gp_files/QLP-all-supplementary-files/Guitar Pro Files")

        for idx, page in enumerate(pages):
            chapter_num = idx + 1
            lesson_num = CHAPTER_TO_LESSON.get(chapter_num)
            video_filename = f"lesson_{lesson_num:02d}.webm" if lesson_num else None

            pdf_file = find_matching_file(page.title, pdf_dir, ".pdf")
            gp_file = find_matching_file(page.title, gp_dir, ".gp")

            self.stdout.write(f"\n  [{chapter_num:02d}] {page.title} (pk={page.pk})")
            self.stdout.write(f"       Video: {video_filename or 'NONE'}")
            self.stdout.write(f"       PDF:   {pdf_file.name if pdf_file else 'NONE'}")
            self.stdout.write(f"       GP:    {gp_file.name if gp_file else 'NONE'}")

            if dry_run:
                continue

            # --- Clean and rebuild body HTML ---
            clean_body = strip_redundant_lines(page.body or "")

            parts = []
            # Video player at top of body
            if video_filename:
                video_url = f"/media/videos/quick-lessons-pro/{video_filename}"
                parts.append(
                    f'<div style="position:relative;width:100%;margin:0 0 1.5rem 0;">'
                    f'<video controls playsinline preload="metadata" '
                    f'style="width:100%;border-radius:0.5rem;background:#000;">'
                    f'<source src="{html.escape(video_url)}" type="video/webm">'
                    f'Tu navegador no soporta la reproducci\u00f3n de v\u00eddeo.'
                    f'</video></div>'
                )
            if clean_body:
                parts.append(clean_body)

            page.body = "\n".join(parts)

            # --- Build attachments: video + PDF + GP ---
            attachment_blocks = []

            # Video as Document (reference existing media file, no copy)
            if video_filename:
                video_doc = get_or_create_doc(
                    f"{page.title} — Video",
                    media_relative=f"videos/quick-lessons-pro/{video_filename}",
                    stdout=self.stdout,
                )
                if video_doc:
                    attachment_blocks.append(("video", {"video_file": video_doc}))

            # PDF
            if pdf_file:
                pdf_doc = get_or_create_doc(
                    f"{page.title} — PDF",
                    file_path=pdf_file,
                    stdout=self.stdout,
                )
                if pdf_doc:
                    attachment_blocks.append(("pdf_score", {"pdf_file": pdf_doc}))

            # GP file
            if gp_file:
                gp_doc = get_or_create_doc(
                    f"{page.title} — Guitar Pro",
                    file_path=gp_file,
                    stdout=self.stdout,
                )
                if gp_doc:
                    attachment_blocks.append(("pdf_score", {"pdf_file": gp_doc}))

            page.attachments = attachment_blocks
            page.save_revision().publish()
            self.stdout.write(self.style.SUCCESS(f"       Updated and published"))

        self.stdout.write(self.style.SUCCESS(f"\nDone! Updated {len(pages)} chapters."))
