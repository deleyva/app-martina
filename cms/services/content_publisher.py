"""
Content Publisher Service

Creates ScorePages in Wagtail from AI-extracted metadata and uploaded files.
"""

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from wagtail.documents import get_document_model
from wagtail.images import get_image_model
from wagtail.models import Page

from cms.models import (
    MusicCategory,
    MusicComposer,
    MusicLibraryIndexPage,
    MusicTag,
    ScorePage,
)

logger = logging.getLogger(__name__)

User = get_user_model()
Document = get_document_model()
Image = get_image_model()


class ContentPublisher:
    """
    Create ScorePage in Wagtail from AI-extracted metadata and uploaded files.
    """

    def __init__(self, user: User):
        """
        Initialize the content publisher.

        Args:
            user: The user creating the content
        """
        self.user = user

    @transaction.atomic
    def create_scorepage_from_ai(
        self,
        metadata: dict[str, Any],
        pdf_files: list[UploadedFile],
        audio_files: list[UploadedFile],
        image_files: list[UploadedFile],
        midi_files: list[UploadedFile],
        publish: bool = False,
        parent_page: MusicLibraryIndexPage = None,
    ) -> ScorePage:
        """
        Create ScorePage from AI-extracted metadata and uploaded files.

        Args:
            metadata: Dictionary with extracted metadata fields
            pdf_files: List of PDF files
            audio_files: List of audio files
            image_files: List of image files
            midi_files: List of MIDI files
            publish: If True, publish immediately; if False, save as draft
            parent_page: Parent page for the ScorePage (defaults to first MusicLibraryIndexPage)

        Returns:
            Created ScorePage instance

        Raises:
            ValueError: If parent page doesn't exist
            RuntimeError: If creation fails
        """
        logger.info(f"Creating ScorePage from AI metadata: {metadata.get('title', 'N/A')}")

        try:
            # Get or create parent page
            if parent_page is None:
                parent_page = MusicLibraryIndexPage.objects.live().first()
                if not parent_page:
                    raise ValueError("No MusicLibraryIndexPage found. Please create one first.")

            # Get or create composer
            composer = None
            if metadata.get("composer"):
                composer = self._get_or_create_composer(metadata["composer"])

            # Create Wagtail documents and images
            documents = {
                "pdfs": [
                    self._create_wagtail_document(
                        pdf, title=f"{metadata.get('title', 'PDF')} - {i+1}"
                    )
                    for i, pdf in enumerate(pdf_files)
                ],
                "audios": [
                    self._create_wagtail_document(
                        audio, title=f"{metadata.get('title', 'Audio')} - {i+1}"
                    )
                    for i, audio in enumerate(audio_files)
                ],
                "midis": [
                    self._create_wagtail_document(
                        midi, title=f"{metadata.get('title', 'MIDI')} - {i+1}"
                    )
                    for i, midi in enumerate(midi_files)
                ],
            }

            images = [
                self._create_wagtail_image(
                    img, title=f"{metadata.get('title', 'Imagen')} - {i+1}"
                )
                for i, img in enumerate(image_files)
            ]

            # Build StreamField content
            streamfield_content = self._build_streamfield_content(
                metadata, documents, images
            )

            # Create ScorePage
            title = metadata.get("title", "Sin título")
            slug = self._generate_unique_slug(title, parent_page)

            score_page = ScorePage(
                title=title,
                slug=slug,
                composer=composer,
                content=streamfield_content,
                owner=self.user,
            )

            # Add as child of parent page
            parent_page.add_child(instance=score_page)

            # Get or create categories and tags
            if metadata.get("categories"):
                categories = [
                    self._get_or_create_category(cat) for cat in metadata["categories"]
                ]
                score_page.categories.set(categories)

            if metadata.get("tags"):
                tags = [self._get_or_create_tag(tag) for tag in metadata["tags"]]
                score_page.tags.set(tags)

            # Save and optionally publish
            score_page.save()

            if publish:
                score_page.save_revision().publish()
                logger.info(f"Published ScorePage: {score_page.title} (ID: {score_page.id})")
            else:
                score_page.save_revision()
                logger.info(
                    f"Created draft ScorePage: {score_page.title} (ID: {score_page.id})"
                )

            return score_page

        except Exception as e:
            logger.error(f"Failed to create ScorePage: {e}")
            raise RuntimeError(f"Failed to create ScorePage: {e}") from e

    def _get_or_create_composer(self, name: str) -> MusicComposer:
        """
        Get existing composer or create a new one.

        Args:
            name: Composer name

        Returns:
            MusicComposer instance
        """
        if not name or not name.strip():
            return None

        # Normalize name (capitalize words)
        normalized_name = " ".join(word.capitalize() for word in name.split())

        # Search for existing composer (case-insensitive)
        composer = MusicComposer.objects.filter(name__iexact=normalized_name).first()

        if composer:
            logger.debug(f"Found existing composer: {composer.name}")
            return composer

        # Create new composer
        composer = MusicComposer.objects.create(
            name=normalized_name,
            bio=f"Compositor añadido automáticamente vía IA el {timezone.now().date()}",
        )
        logger.info(f"Created new composer: {composer.name}")
        return composer

    def _get_or_create_category(self, name: str) -> MusicCategory:
        """
        Get existing category or create a new one.

        Args:
            name: Category name

        Returns:
            MusicCategory instance
        """
        if not name or not name.strip():
            return None

        # Normalize name (capitalize first letter)
        normalized_name = name.strip().capitalize()

        # Search for existing category (case-insensitive)
        category = MusicCategory.objects.filter(
            name__iexact=normalized_name, parent__isnull=True  # Only root categories
        ).first()

        if category:
            logger.debug(f"Found existing category: {category.name}")
            return category

        # Create new category
        category = MusicCategory.objects.create(
            name=normalized_name,
            description=f"Categoría añadida automáticamente vía IA el {timezone.now().date()}",
        )
        logger.info(f"Created new category: {category.name}")
        return category

    def _get_or_create_tag(self, name: str) -> MusicTag:
        """
        Get existing tag or create a new one.

        Args:
            name: Tag name

        Returns:
            MusicTag instance
        """
        if not name or not name.strip():
            return None

        # Normalize name (lowercase)
        normalized_name = name.strip().lower()

        # Search for existing tag (case-insensitive)
        tag = MusicTag.objects.filter(name__iexact=normalized_name).first()

        if tag:
            logger.debug(f"Found existing tag: {tag.name}")
            return tag

        # Create new tag with random color
        import random

        colors = [
            "#3B82F6",  # Blue
            "#10B981",  # Green
            "#F59E0B",  # Amber
            "#EF4444",  # Red
            "#8B5CF6",  # Purple
            "#EC4899",  # Pink
            "#14B8A6",  # Teal
            "#F97316",  # Orange
        ]
        tag = MusicTag.objects.create(
            name=normalized_name, color=random.choice(colors)
        )
        logger.info(f"Created new tag: {tag.name}")
        return tag

    def _create_wagtail_document(self, file: UploadedFile, title: str) -> Document:
        """
        Create Wagtail Document from uploaded file.

        Args:
            file: Uploaded file
            title: Document title

        Returns:
            Document instance
        """
        document = Document(
            title=title,
            file=file,
            uploaded_by_user=self.user,
        )
        document.save()
        logger.debug(f"Created document: {document.title} (ID: {document.id})")
        return document

    def _create_wagtail_image(self, file: UploadedFile, title: str) -> Image:
        """
        Create Wagtail Image from uploaded file.

        Args:
            file: Uploaded image file
            title: Image title

        Returns:
            Image instance
        """
        image = Image(
            title=title,
            file=file,
            uploaded_by_user=self.user,
        )
        image.save()
        logger.debug(f"Created image: {image.title} (ID: {image.id})")
        return image

    def _build_streamfield_content(
        self,
        metadata: dict[str, Any],
        documents: dict[str, list[Document]],
        images: list[Image],
    ) -> list:
        """
        Build StreamField content from metadata and files.

        Args:
            metadata: Extracted metadata dictionary
            documents: Dictionary with 'pdfs', 'audios', 'midis' lists
            images: List of Image instances

        Returns:
            List of tuples (block_type, block_value) for StreamField
        """
        content = []

        # Block 1: PDF principal
        if documents.get("pdfs"):
            for pdf_doc in documents["pdfs"]:
                content.append(
                    (
                        "pdf_score",
                        {
                            "title": metadata.get("title", "Partitura"),
                            "pdf_file": pdf_doc,
                            "description": metadata.get("description", ""),
                            "page_count": "",
                        },
                    )
                )

        # Block 2: Metadata musical (si hay campos)
        if any(
            [
                metadata.get("key_signature"),
                metadata.get("tempo"),
                metadata.get("time_signature"),
                metadata.get("difficulty"),
            ]
        ):
            duration_str = ""
            if metadata.get("duration_minutes"):
                duration_str = str(metadata["duration_minutes"])

            content.append(
                (
                    "metadata",
                    {
                        "composer": "",  # Ya está en el campo principal de ScorePage
                        "key_signature": metadata.get("key_signature", ""),
                        "tempo": metadata.get("tempo", ""),
                        "difficulty": metadata.get("difficulty", ""),
                        "duration_minutes": duration_str,
                        "reference": metadata.get("reference_catalog", ""),
                    },
                )
            )

        # Block 3: Notas (si existen)
        if metadata.get("notes"):
            content.append(("notes", metadata["notes"]))

        # Block 4: Audios
        for audio_doc in documents.get("audios", []):
            content.append(
                (
                    "audio",
                    {
                        "title": audio_doc.title,
                        "audio_file": audio_doc,
                        "description": "",
                    },
                )
            )

        # Block 5: Archivos MIDI (como audio)
        for midi_doc in documents.get("midis", []):
            content.append(
                (
                    "audio",
                    {
                        "title": midi_doc.title,
                        "audio_file": midi_doc,
                        "description": "Archivo MIDI",
                    },
                )
            )

        # Block 6: Imágenes
        for image in images:
            content.append(
                (
                    "image",
                    {
                        "title": image.title,
                        "image": image,
                        "caption": "",
                    },
                )
            )

        # Block 7: Embed (si existe)
        if metadata.get("embed_url"):
            content.append(("embed", metadata["embed_url"]))

        return content

    def _generate_unique_slug(self, title: str, parent_page: Page) -> str:
        """
        Generate a unique slug for the page.

        Args:
            title: Page title
            parent_page: Parent page

        Returns:
            Unique slug
        """
        base_slug = slugify(title)
        if not base_slug:
            base_slug = "score"

        slug = base_slug
        counter = 1

        # Check if slug exists under parent
        while parent_page.get_children().filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug
