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
    DictadoPage,
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

            # Check for existing ScorePage with same title
            title = metadata.get("title", "Sin título")
            existing_page = self._find_existing_scorepage(title, parent_page)
            
            if existing_page:
                logger.info(f"Found existing ScorePage: {existing_page.title} (ID: {existing_page.id}). Appending files.")
                return self._append_files_to_scorepage(
                    existing_page, metadata, pdf_files, audio_files, image_files, midi_files, publish
                )

            # Get or create composer
            composer = None
            if metadata.get("composer"):
                composer = self._get_or_create_composer(metadata["composer"])

            # Create Wagtail documents and images with automatic tagging
            base_title = metadata.get('title', 'Sin título')
            
            documents = {
                "pdfs": [],
                "audios": [],
                "midis": [],
            }
            
            for i, pdf in enumerate(pdf_files):
                # Merge filename-based tags with AI-suggested tags
                filename_tags = self._extract_tags_from_filename(pdf.name)
                ai_tags = self._get_ai_suggested_tags(metadata, pdf.name)
                all_tags = list(set(filename_tags + ai_tags))  # Deduplicate
                
                title = self._generate_descriptive_title(base_title, pdf.name, all_tags)
                doc = self._create_wagtail_document(pdf, title=title, tags=all_tags)
                documents["pdfs"].append(doc)
            
            for i, audio in enumerate(audio_files):
                filename_tags = self._extract_tags_from_filename(audio.name)
                ai_tags = self._get_ai_suggested_tags(metadata, audio.name)
                all_tags = list(set(filename_tags + ai_tags))
                
                title = self._generate_descriptive_title(base_title, audio.name, all_tags)
                doc = self._create_wagtail_document(audio, title=title, tags=all_tags)
                documents["audios"].append(doc)
            
            for i, midi in enumerate(midi_files):
                filename_tags = self._extract_tags_from_filename(midi.name)
                ai_tags = self._get_ai_suggested_tags(metadata, midi.name)
                all_tags = list(set(filename_tags + ai_tags))
                
                title = self._generate_descriptive_title(base_title, midi.name, all_tags)
                doc = self._create_wagtail_document(midi, title=title, tags=all_tags)
                documents["midis"].append(doc)

            images = []
            for i, img in enumerate(image_files):
                filename_tags = self._extract_tags_from_filename(img.name)
                ai_tags = self._get_ai_suggested_tags(metadata, img.name)
                all_tags = list(set(filename_tags + ai_tags))
                
                title = self._generate_descriptive_title(base_title, img.name, all_tags)
                image = self._create_wagtail_image(img, title=title, tags=all_tags)
                images.append(image)

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

    def _find_existing_scorepage(
        self, title: str, parent_page: Page
    ) -> ScorePage | None:
        """
        Search for existing ScorePage with same title under the given parent.

        Args:
            title: Title to search for
            parent_page: Parent page to search under

        Returns:
            Existing ScorePage if found, None otherwise
        """
        if not title or title == "Sin título":
            return None

        # Search for existing page (case-insensitive) within the same parent
        existing = ScorePage.objects.child_of(parent_page).filter(
            title__iexact=title
        ).first()

        return existing

    def _append_files_to_scorepage(
        self,
        score_page: ScorePage,
        metadata: dict[str, Any],
        pdf_files: list[UploadedFile],
        audio_files: list[UploadedFile],
        image_files: list[UploadedFile],
        midi_files: list[UploadedFile],
        publish: bool = False,
    ) -> ScorePage:
        """
        Append new files to an existing ScorePage.

        Args:
            score_page: Existing ScorePage to update
            metadata: Metadata dict (for file titles)
            pdf_files: PDF files to add
            audio_files: Audio files to add
            image_files: Image files to add
            midi_files: MIDI files to add
            publish: Whether to publish after updating

        Returns:
            Updated ScorePage
        """
        logger.info(f"Appending files to existing ScorePage: {score_page.title}")

        # Create new documents and images with automatic tagging and descriptive titles
        base_title = score_page.title
        
        new_pdfs = []
        for i, pdf in enumerate(pdf_files):
            tags = self._extract_tags_from_filename(pdf.name)
            title = self._generate_descriptive_title(base_title, pdf.name, tags)
            doc = self._create_wagtail_document(pdf, title=title, tags=tags)
            new_pdfs.append(doc)
        
        new_audios = []
        for i, audio in enumerate(audio_files):
            tags = self._extract_tags_from_filename(audio.name)
            title = self._generate_descriptive_title(base_title, audio.name, tags)
            doc = self._create_wagtail_document(audio, title=title, tags=tags)
            new_audios.append(doc)
        
        new_midis = []
        for i, midi in enumerate(midi_files):
            tags = self._extract_tags_from_filename(midi.name)
            title = self._generate_descriptive_title(base_title, midi.name, tags)
            doc = self._create_wagtail_document(midi, title=title, tags=tags)
            new_midis.append(doc)
        
        new_images = []
        for i, img in enumerate(image_files):
            tags = self._extract_tags_from_filename(img.name)
            title = self._generate_descriptive_title(base_title, img.name, tags)
            image = self._create_wagtail_image(img, title=title, tags=tags)
            new_images.append(image)

        # Append to existing StreamField content
        content = score_page.content

        # Add PDFs
        for pdf_doc in new_pdfs:
            content.append(("pdf_score", {"pdf_file": pdf_doc}))

        # Add audio files
        for audio_doc in new_audios:
            content.append(("audio", {"audio_file": audio_doc}))

        # Add MIDI files
        for midi_doc in new_midis:
            content.append(("midi", {"midi_file": midi_doc}))

        # Add images
        for img in new_images:
            content.append(("image", {"image": img}))

        score_page.content = content
        score_page.save()

        if publish:
            score_page.save_revision().publish()
            logger.info(f"Published updated ScorePage: {score_page.title}")
        else:
            score_page.save_revision()
            logger.info(f"Saved updated draft ScorePage: {score_page.title}")

        return score_page

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

    KNOWN_INSTRUMENTS = {
        "piano",
        "guitarra",
        "bajo",
        "batería",
        "bateria",
        "voz",
        "coro",
        "saxofón",
        "saxofon",
        "ukelele",
        "violín",
        "violin",
        "flauta",
        "clarinete",
        "trompeta",
        "trombón",
        "trombon",
    }

    KNOWN_GENRES = {
        "jazz",
        "blues",
        "rock",
        "pop",
        "clásica",
        "clasica",
        "folk",
        "worksongs",
        "villancico",
        "jota",
        "soul",
        "funk",
        "metal",
        "bossa nova",
        "bossa",
    }

    def _get_or_create_category(self, name: str) -> MusicCategory:
        """
        Get existing category or create a new one, organizing by hierarchy.

        Args:
            name: Category name

        Returns:
            MusicCategory instance
        """
        if not name or not name.strip():
            return None

        # Normalize name (capitalize first letter)
        normalized_name = name.strip().capitalize()
        name_lower = normalized_name.lower()

        # Determine parent based on known lists
        parent = None
        if name_lower in self.KNOWN_INSTRUMENTS:
            parent, _ = MusicCategory.objects.get_or_create(
                name="Instrumentos", defaults={"parent": None}
            )
        elif name_lower in self.KNOWN_GENRES:
            parent, _ = MusicCategory.objects.get_or_create(
                name="Géneros", defaults={"parent": None}
            )

        # Search for existing category
        if parent:
            category = MusicCategory.objects.filter(
                name__iexact=normalized_name, parent=parent
            ).first()
        else:
            # Fallback for generic categories or if no parent matched
            category = MusicCategory.objects.filter(
                name__iexact=normalized_name, parent=None
            ).first()

        if category:
            logger.debug(f"Found existing category: {category.name}")
            return category

        # Create new category
        category = MusicCategory.objects.create(
            name=normalized_name,
            parent=parent,
            description=f"Categoría añadida automáticamente vía IA el {timezone.now().date()}",
        )
        logger.info(f"Created new category: {category.name} (Parent: {parent})")
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

    def _create_wagtail_document(
        self, file: UploadedFile, title: str, tags: list[str] = None
    ) -> Document:
        """
        Create Wagtail Document from uploaded file.

        Args:
            file: Uploaded file
            title: Document title
            tags: Optional list of tag names to apply (namespace format supported)

        Returns:
            Document instance
        """
        document = Document(
            title=title,
            file=file,
            uploaded_by_user=self.user,
        )
        document.save()
        
        # Apply tags if provided
        if tags:
            self._apply_tags_to_document(document, tags)
        
        logger.debug(f"Created document: {document.title} (ID: {document.id})")
        return document

    def _create_wagtail_image(
        self, file: UploadedFile, title: str, tags: list[str] = None
    ) -> Image:
        """
        Create Wagtail Image from uploaded file.

        Args:
            file: Uploaded image file
            title: Image title
            tags: Optional list of tag names to apply (namespace format supported)

        Returns:
            Image instance
        """
        image = Image(
            title=title,
            file=file,
            uploaded_by_user=self.user,
        )
        image.save()
        
        # Apply tags if provided
        if tags:
            self._apply_tags_to_image(image, tags)
        
        logger.debug(f"Created image: {image.title} (ID: {image.id})")
        return image

    def _extract_tags_from_filename(self, filename: str) -> list[str]:
        """
        Extract namespace tags from filename patterns.

        Examples:
            'partitura_tenor.pdf' -> ['voice/tenor']
            'guitarra_acordes.pdf' -> ['instrument/guitar', 'type/chordsheet']
            'piano_facil.pdf' -> ['instrument/piano']

        Args:
            filename: Original filename

        Returns:
            List of namespace tags
        """
        filename_lower = filename.lower()
        tags = []

        # Instrument detection (check first to take priority)
        instrument_patterns = {
            'piano': 'instrument/piano',
            'guitarra': 'instrument/guitar',
            'guitar': 'instrument/guitar',
            'bateria': 'instrument/drums',
            'drums': 'instrument/drums',
            'violin': 'instrument/violin',
            'cello': 'instrument/cello',
            'flauta': 'instrument/flute',
            'saxo': 'instrument/saxophone',
        }
        for keyword, tag in instrument_patterns.items():
            if keyword in filename_lower:
                tags.append(tag)

        # Special handling for 'bass/bajo' - context-dependent
        if 'bass' in filename_lower or 'bajo' in filename_lower:
            # If contains voice-related keywords, it's a voice part
            if any(word in filename_lower for word in ['voice', 'vocal', 'voz', 'coro', 'choir']):
                tags.append('voice/bass')
            else:
                # Default to instrument
                tags.append('instrument/bass')

        # Voice/Part detection (excluding bass, handled above)
        voice_patterns = {
            'tenor': 'voice/tenor',
            'soprano': 'voice/soprano',
            'alto': 'voice/alto',
            'baritono': 'voice/baritone',
        }
        for keyword, tag in voice_patterns.items():
            if keyword in filename_lower:
                tags.append(tag)

        # Type detection
        if 'acorde' in filename_lower or 'chord' in filename_lower:
            tags.append('type/chordsheet')
        if 'tab' in filename_lower or 'tablatura' in filename_lower:
            tags.append('type/tab')
        if 'partitura' in filename_lower or 'score' in filename_lower:
            tags.append('type/score')

        return tags

    def _normalize_tag_name(self, tag_name: str) -> str:
        """
        Normalize tag name to consistent lowercase format.

        Args:
            tag_name: Original tag name

        Returns:
            Normalized tag name (lowercase, trimmed)
        """
        return tag_name.lower().strip()

    def _find_existing_tag(self, tag_name: str) -> str | None:
        """
        Find existing tag with case-insensitive match.
        Returns the canonical tag name if found, None otherwise.

        Args:
            tag_name: Tag name to search for

        Returns:
            Canonical tag name if exists, None otherwise
        """
        normalized = self._normalize_tag_name(tag_name)
        
        # Search in taggit's Tag model (case-insensitive)
        from taggit.models import Tag
        existing = Tag.objects.filter(name__iexact=normalized).first()
        
        if existing:
            return existing.name  # Return canonical version
        
        return None

    def _apply_tags_to_document(self, document: Document, tag_names: list[str]):
        """
        Apply tags to a Wagtail Document with normalization.
        Searches for existing tags case-insensitively to maintain consistency.

        Args:
            document: Document instance
            tag_names: List of tag names (can include namespace format)
        """
        if not tag_names:
            return

        # Normalize and apply tags
        for tag_name in tag_names:
            # Try to find existing tag (case-insensitive)
            existing = self._find_existing_tag(tag_name)
            canonical_name = existing if existing else self._normalize_tag_name(tag_name)
            
            # Add canonical tag (reuses existing or creates normalized new one)
            document.tags.add(canonical_name)
        
        # Save to persist tags
        document.save()
        
        logger.debug(f"Applied tags to document {document.id}: {tag_names}")

    def _apply_tags_to_image(self, image: Image, tag_names: list[str]):
        """
        Apply tags to a Wagtail Image with normalization.
        Searches for existing tags case-insensitively to maintain consistency.

        Args:
            image: Image instance
            tag_names: List of tag names (can include namespace format)
        """
        if not tag_names:
            return

        # Normalize and apply tags
        for tag_name in tag_names:
            # Try to find existing tag (case-insensitive)
            existing = self._find_existing_tag(tag_name)
            canonical_name = existing if existing else self._normalize_tag_name(tag_name)
            
            # Add canonical tag (reuses existing or creates normalized new one)
            image.tags.add(canonical_name)
        
        # Save to persist tags
        image.save()
        
        logger.debug(f"Applied tags to image {image.id}: {tag_names}")

    def _generate_descriptive_title(
        self, base_title: str, filename: str, tags: list[str]
    ) -> str:
        """
        Generate a descriptive title for a document based on extracted tags.

        Examples:
            base_title="Si te vas", tags=["voice/tenor"] → "Si te vas tenor"
            base_title="Si te vas", tags=["instrument/guitar"] → "Si te vas guitar"
            base_title="Si te vas", tags=["instrument/piano", "type/chordsheet"] → "Si te vas piano chordsheet"

        Args:
            base_title: Base title (usually song name)
            filename: Original filename
            tags: List of namespace tags

        Returns:
            Descriptive title string
        """
        if not tags:
            return base_title

        # Extract meaningful parts from tags
        descriptors = []
        for tag in tags:
            # Split namespace tags (e.g., "instrument/piano" → "piano")
            if "/" in tag:
                _, descriptor = tag.split("/", 1)
                descriptors.append(descriptor)
            else:
                descriptors.append(tag)

        # Join descriptors with title
        if descriptors:
            return f"{base_title} {' '.join(descriptors)}"
        
        return base_title

    def _get_ai_suggested_tags(self, metadata: dict[str, Any], filename: str) -> list[str]:
        """
        Get AI-suggested tags for a specific file from metadata.

        Args:
            metadata: Full metadata dict from AI extraction
            filename: Name of the file to get tags for

        Returns:
            List of AI-suggested namespace tags for this file
        """
        files_metadata = metadata.get("files", [])
        
        # Try to find AI-specific tags for this file
        if files_metadata:
            for file_meta in files_metadata:
                if file_meta.get("filename", "").lower() in filename.lower() or \
                   filename.lower() in file_meta.get("filename", "").lower():
                    ai_tags = file_meta.get("tags", [])
                    if ai_tags:
                        return ai_tags
        
        # Fallback: Extract tags from description and categories
        return self._extract_tags_from_description(metadata)

    def _extract_tags_from_description(self, metadata: dict[str, Any]) -> list[str]:
        """
        Extract namespace tags by analyzing the description and categories.
        This is a fallback when AI doesn't provide file-specific tags.

        Args:
            metadata: Full metadata dict from AI extraction

        Returns:
            List of inferred namespace tags
        """
        tags = []
        description = metadata.get("description", "").lower()
        categories = [cat.lower() for cat in metadata.get("categories", [])]
        
        # Voice parts detection from description
        voice_keywords = {
            "soprano": "voice/soprano",
            "alto": "voice/alto",
            "tenor": "voice/tenor",
            "bajo": "voice/bass",
            "bass": "voice/bass",
            "baritone": "voice/baritone",
            "barítono": "voice/baritone",
            "coro": "voice/choir",
            "choir": "voice/choir",
            "satb": "voice/satb",
        }
        for keyword, tag in voice_keywords.items():
            if keyword in description:
                tags.append(tag)
        
        # Instrument detection from categories and description
        instrument_keywords = {
            "piano": "instrument/piano",
            "guitarra": "instrument/guitar",
            "guitar": "instrument/guitar",
            "bateria": "instrument/drums",
            "drums": "instrument/drums",
            "violin": "instrument/violin",
            "cello": "instrument/cello",
            "flauta": "instrument/flute",
            "saxo": "instrument/saxophone",
            "saxophone": "instrument/saxophone",
        }
        for keyword, tag in instrument_keywords.items():
            if keyword in description or keyword in " ".join(categories):
                tags.append(tag)
        
        # Type detection from description
        if "acompañamiento" in description or "accompaniment" in description:
            tags.append("type/accompaniment")
        if "partitura" in description or "score" in description:
            tags.append("type/score")
        if "acorde" in description or "chord" in description:
            tags.append("type/chordsheet")
        if "tablatura" in description or "tab" in description:
            tags.append("type/tab")
        
        return tags

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
                            "title": pdf_doc.title,  # Use document's actual title
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

    @transaction.atomic
    def create_dictadopage_from_ai(
        self,
        metadata: dict[str, Any],
        pdf_files: list[UploadedFile],
        audio_files: list[UploadedFile],
        image_files: list[UploadedFile],
        midi_files: list[UploadedFile],
        publish: bool = False,
        parent_page: MusicLibraryIndexPage = None,
    ) -> 'DictadoPage':
        """
        Create DictadoPage from AI-extracted metadata and uploaded files.
        
        DictadoPage uses a StreamField with:
        - audio blocks (WaveSurfer.js player)
        - answer_image blocks (collapsible image answers)
        - answer_pdf blocks (collapsible PDF answers)
        
        Args:
            metadata: Dictionary with extracted metadata
            pdf_files: List of PDF files (used as answers)
            audio_files: List of audio files
            image_files: List of image files (used as answers)
            midi_files: List of MIDI files (converted to audio)
            publish: If True, publish immediately; if False, save as draft
            parent_page: Parent page for the DictadoPage
            
        Returns:
            Created DictadoPage instance
        """
        logger.info(f"Creating DictadoPage from AI metadata: {metadata.get('title', 'N/A')}")
        
        try:
            # Get or create parent page
            if parent_page is None:
                parent_page = MusicLibraryIndexPage.objects.live().first()
                if not parent_page:
                    raise ValueError("No MusicLibraryIndexPage found. Please create one first.")
            
            # Create Wagtail documents and images
            base_title = metadata.get('title', 'Sin título')
            
            # Create audio documents
            audio_docs = []
            for i, audio in enumerate(audio_files):
                filename_tags = self._extract_tags_from_filename(audio.name)
                ai_tags = self._get_ai_suggested_tags(metadata, audio.name)
                all_tags = list(set(filename_tags + ai_tags))
                title = self._generate_descriptive_title(base_title, audio.name, all_tags)
                doc = self._create_wagtail_document(audio, title=title, tags=all_tags)
                audio_docs.append(doc)
            
            # MIDI files as audio
            for i, midi in enumerate(midi_files):
                filename_tags = self._extract_tags_from_filename(midi.name)
                ai_tags = self._get_ai_suggested_tags(metadata, midi.name)
                all_tags = list(set(filename_tags + ai_tags))
                title = self._generate_descriptive_title(base_title, midi.name, all_tags)
                doc = self._create_wagtail_document(midi, title=title, tags=all_tags)
                audio_docs.append(doc)
            
            # Create PDF documents (for answers)
            pdf_docs = []
            for i, pdf in enumerate(pdf_files):
                filename_tags = self._extract_tags_from_filename(pdf.name)
                ai_tags = self._get_ai_suggested_tags(metadata, pdf.name)
                all_tags = list(set(filename_tags + ai_tags))
                title = self._generate_descriptive_title(base_title, pdf.name, all_tags)
                doc = self._create_wagtail_document(pdf, title=title, tags=all_tags)
                pdf_docs.append(doc)
            
            # Create images (for answers)
            answer_images = []
            for i, img in enumerate(image_files):
                filename_tags = self._extract_tags_from_filename(img.name)
                ai_tags = self._get_ai_suggested_tags(metadata, img.name)
                all_tags = list(set(filename_tags + ai_tags))
                title = self._generate_descriptive_title(base_title, img.name, all_tags)
                image = self._create_wagtail_image(img, title=title, tags=all_tags)
                answer_images.append(image)
            
            # Build StreamField content for DictadoPage
            content = []
            
            # Add audio blocks first
            for audio_doc in audio_docs:
                content.append((
                    'audio',
                    {
                        'title': audio_doc.title,
                        'audio_file': audio_doc,
                        'description': metadata.get('description', ''),
                    }
                ))
            
            # Add answer images (collapsible)
            for image in answer_images:
                content.append((
                    'answer_image',
                    {
                        'title': 'Ver respuesta',
                        'image': image,
                        'caption': '',
                        'is_collapsed': True,
                    }
                ))
            
            # Add answer PDFs (collapsible)
            for pdf_doc in pdf_docs:
                content.append((
                    'answer_pdf',
                    {
                        'title': 'Ver partitura',
                        'pdf': pdf_doc,
                        'description': '',
                        'is_collapsed': True,
                    }
                ))
            
            # Create DictadoPage
            title = metadata.get('title', 'Sin título')
            slug = self._generate_unique_slug(title, parent_page)
            
            dictado_page = DictadoPage(
                title=title,
                slug=slug,
                date=timezone.now().date(),
                intro=metadata.get('description', ''),
                content=content,
                owner=self.user,
            )
            
            # Add as child of parent page
            parent_page.add_child(instance=dictado_page)
            
            # Get or create categories and tags
            if metadata.get('categories'):
                categories = [
                    self._get_or_create_category(cat) for cat in metadata['categories']
                ]
                dictado_page.categories.set(categories)
            
            if metadata.get('tags'):
                tags = [self._get_or_create_tag(tag) for tag in metadata['tags']]
                dictado_page.tags.set(tags)
            
            # Save and optionally publish
            dictado_page.save()
            
            if publish:
                dictado_page.save_revision().publish()
                logger.info(f"Published DictadoPage: {dictado_page.title} (ID: {dictado_page.id})")
            else:
                dictado_page.save_revision()
                logger.info(f"Created draft DictadoPage: {dictado_page.title} (ID: {dictado_page.id})")
            
            return dictado_page
            
        except Exception as e:
            logger.error(f"Failed to create DictadoPage: {e}")
            raise RuntimeError(f"Failed to create DictadoPage: {e}") from e
