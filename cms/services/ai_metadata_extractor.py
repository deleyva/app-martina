"""
AI Metadata Extractor Service

Uses Google Gemini to extract structured metadata from natural language descriptions
of musical content.
"""

import json
import logging
from typing import Any

from django.conf import settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class AIMetadataExtractor:
    """
    Extract structured metadata from natural language descriptions using Google Gemini.
    """

    PROMPT_TEMPLATE = """Eres un asistente experto en catalogación musical y musicología. El usuario ha subido archivos musicales y ha proporcionado una descripción.

DESCRIPCIÓN ORIGINAL:
{description}

ARCHIVOS SUBIDOS:
{file_names}

Tu tarea es extraer y NORMALIZAR la información. Usa tu CONOCIMIENTO INTERNO sobre música para:
1. Corregir nombres de artistas (ej: "Extremo Duro" -> "Extremoduro").
2. Separar claramente Título de Compositor.
3. Analizar la descripción para asignar etiquetas específicas a cada archivo.

Formato JSON requerido:

{{
  "title": "Título CORRECTO y estandarizado de la obra",
  "composer": "Nombre CORRECTO del compositor/artista",
  "key_signature": "Tonalidad en Notación Inglesa (ej: C, Am, F#, Bb)",
  "tempo": "Indicación de tempo (ej: Allegro, 120 BPM)",
  "time_signature": "Compás (ej: 4/4, 3/4)",
  "difficulty": "beginner, easy, intermediate, advanced, o expert",
  "duration_minutes": Duración aproximada en minutos (número o null),
  "reference_catalog": "Número de catálogo si aplica",
  "categories": ["Instrumentos", "Géneros", "Formaciones"],
  "tags": ["Etiquetas descriptivas", "mood", "técnica"],
  "files": [
    {{
      "filename": "nombre_del_archivo.pdf",
      "tags": ["etiquetas", "específicas", "para", "este", "archivo"]
    }}
  ],
  "description": "Descripción profesional mejorada",
  "notes": "Consejos de interpretación"
}}

REGLAS CRÍTICAS:
- **Corrección de Entidades**: Si el usuario escribe mal el nombre de una canción o grupo famoso, CORRÍGELO.
- **Tonalidad**: Usa SIEMPRE Notación Inglesa estándar (ej: "F", "Fm", "C#", "Bb").
- CATEGORÍAS: Instrumentos y Géneros van aquí ("Piano", "Rock", "Coro").
- TAGS: Descriptores de técnica, ocasión, mood. NO incluyas instrumentos/géneros.

**MUY IMPORTANTE - ARRAY 'files' OBLIGATORIO**:
DEBES incluir SIEMPRE un array 'files' con una entrada por cada archivo subido.
Para cada archivo, analiza la descripción del usuario y asigna etiquetas namespace:

Ejemplos de cómo asignar etiquetas por descripción:
- Descripción: "para coro" → tags: ["voice/choir"]
- Descripción: "incluye soprano, alto, tenor" → tags: ["voice/soprano", "voice/alto", "voice/tenor"]
- Descripción: "piano de acompañamiento" → tags: ["instrument/piano", "type/accompaniment"]
- Descripción: "guitarra acústica" → tags: ["instrument/guitar"]
- Descripción: "partitura para bajo" → tags: ["instrument/bass", "type/score"]

SIEMPRE usa el patrón: instrument/INSTRUMENTO, voice/VOZ, type/TIPO

Responde SOLO con el JSON válido. EL ARRAY 'files' ES OBLIGATORIO.
"""

    DEFAULT_METADATA = {
        "title": "Sin título",
        "composer": "",
        "key_signature": "",
        "tempo": "",
        "time_signature": "",
        "difficulty": "",
        "duration_minutes": None,
        "reference_catalog": "",
        "categories": [],
        "tags": [],
        "files": [],
        "description": "",
        "notes": "",
    }

    def __init__(self):
        """Initialize the AI metadata extractor with Gemini API."""
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY not configured in settings. "
                "Please add it to your .env file."
            )

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # Use Gemini 2.0 Flash model (stable and fast)
        # Note: "gemini-flash-latest" can also be used as an alias to latest version
        self.model_id = "gemini-2.0-flash"

    def extract_metadata(
        self, description: str, file_names: list[str]
    ) -> dict[str, Any]:
        """
        Extract structured metadata from a natural language description.

        Args:
            description: Natural language description of the musical content
            file_names: List of uploaded file names (for context)

        Returns:
            Dictionary with extracted metadata fields

        Raises:
            ValueError: If description is empty
            RuntimeError: If API call fails after retries
        """
        if not description or not description.strip():
            raise ValueError("Description cannot be empty")

        # Format file names for the prompt
        formatted_files = "\n".join(f"- {name}" for name in file_names) if file_names else "- (ningún archivo especificado)"

        # Build the prompt
        prompt = self.PROMPT_TEMPLATE.format(
            description=description.strip(), file_names=formatted_files
        )

        logger.info(
            f"Extracting metadata with AI for description: {description[:100]}..."
        )

        try:
            # Call Gemini API with retry logic
            metadata = self._call_gemini_with_retry(prompt)
            logger.info(
                f"Successfully extracted metadata: title='{metadata.get('title', 'N/A')}', "
                f"composer='{metadata.get('composer', 'N/A')}'"
            )
            return metadata

        except Exception as e:
            logger.error(
                f"Failed to extract metadata after retries: {e}",
                exc_info=True,
                extra={
                    "description": description[:100],
                    "api_key_configured": bool(settings.GEMINI_API_KEY),
                }
            )
            # Return default metadata with original description
            fallback = self.DEFAULT_METADATA.copy()
            fallback["description"] = description
            fallback["notes"] = (
                "⚠️ Metadata automática no disponible. "
                "La API de IA falló. Por favor, completa manualmente."
            )
            logger.warning(
                f"Returning fallback metadata with title='Sin título' - "
                f"This will prevent finding existing pages!"
            )
            return fallback

    def _call_gemini_with_retry(
        self, prompt: str, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Call Gemini API with exponential backoff retry logic.

        Args:
            prompt: The prompt to send to Gemini
            max_retries: Maximum number of retry attempts

        Returns:
            Extracted metadata dictionary

        Raises:
            RuntimeError: If all retries fail
        """
        import time

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,  # Low temperature for consistent output
                        max_output_tokens=2048,
                        response_mime_type="application/json",  # Request JSON response
                    ),
                )

                # Extract text from response
                response_text = response.text.strip()
                logger.debug(f"Gemini API raw response (first 500 chars): {response_text[:500]}")

                # Parse JSON
                metadata = self._parse_json_response(response_text)

                # Validate and normalize metadata
                metadata = self._validate_and_normalize(metadata)

                return metadata

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries}: JSON parsing failed: {e}",
                    extra={"raw_response": response_text[:500] if 'response_text' in locals() else "N/A"}
                )
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                continue

            except Exception as e:
                error_type = type(e).__name__
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries}: API call failed ({error_type}): {e}",
                    exc_info=True
                )
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                continue

        raise RuntimeError(
            f"Failed to extract metadata after {max_retries} attempts"
        )

    def _parse_json_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse JSON response, handling common formatting issues.

        Args:
            response_text: Raw response text from API

        Returns:
            Parsed JSON dictionary

        Raises:
            json.JSONDecodeError: If parsing fails
        """
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith("```"):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith("```"):
            response_text = response_text[:-3]  # Remove trailing ```

        response_text = response_text.strip()

        parsed = json.loads(response_text)
        
        # If AI returned a list (e.g. [metadata]), take the first item
        if isinstance(parsed, list):
            if parsed:
                parsed = parsed[0]
            else:
                return {}
                
        if not isinstance(parsed, dict):
            # If it's still not a dict (e.g. string or number), return empty
            return {}
            
        return parsed

    def _validate_and_normalize(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and normalize extracted metadata.

        Args:
            metadata: Raw metadata dictionary from AI

        Returns:
            Validated and normalized metadata dictionary
        """
        # Start with defaults
        normalized = self.DEFAULT_METADATA.copy()

        # Validate difficulty
        valid_difficulties = {"beginner", "easy", "intermediate", "advanced", "expert"}
        difficulty = metadata.get("difficulty", "").lower()
        if difficulty in valid_difficulties:
            normalized["difficulty"] = difficulty
        else:
            normalized["difficulty"] = ""

        # Validate and normalize strings
        for field in [
            "title",
            "composer",
            "key_signature",
            "tempo",
            "time_signature",
            "reference_catalog",
            "description",
            "notes",
        ]:
            value = metadata.get(field, "")
            normalized[field] = str(value).strip() if value else ""

        # Validate duration_minutes (must be positive integer or null)
        duration = metadata.get("duration_minutes")
        if duration is not None:
            try:
                duration = int(duration)
                if duration > 0:
                    normalized["duration_minutes"] = duration
            except (ValueError, TypeError):
                pass

        # Validate lists
        for field in ["categories", "tags"]:
            value = metadata.get(field, [])
            if isinstance(value, list):
                # Filter out empty strings and deduplicate
                normalized[field] = list(
                    {item.strip() for item in value if item and str(item).strip()}
                )
            else:
                normalized[field] = []

        return normalized
