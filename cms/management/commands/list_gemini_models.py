"""
Django management command to list available Gemini models.

This helps identify which models are available for use with the current API.

Usage:
    python manage.py list_gemini_models
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from google import genai


class Command(BaseCommand):
    help = "List available Gemini models"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=" * 70))
        self.stdout.write(self.style.NOTICE("Available Gemini Models"))
        self.stdout.write(self.style.NOTICE("=" * 70))

        # Check API key configuration
        if not settings.GEMINI_API_KEY:
            self.stdout.write(
                self.style.ERROR(
                    "❌ GEMINI_API_KEY is not configured in settings!"
                )
            )
            return

        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            
            self.stdout.write("\n🔍 Fetching available models...\n")
            
            models = client.models.list()
            
            for model in models:
                model_name = model.name
                # Extract just the model ID (after models/)
                model_id = model_name.split('/')[-1] if '/' in model_name else model_name
                
                supported_actions = []
                if hasattr(model, 'supported_generation_methods'):
                    supported_actions = model.supported_generation_methods
                
                self.stdout.write(f"   📦 {model_id}")
                if supported_actions:
                    self.stdout.write(f"      Supports: {', '.join(supported_actions)}")
                self.stdout.write("")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Failed to list models: {str(e)}")
            )
            self.stdout.write(
                self.style.WARNING(
                    "\nPossible causes:"
                    "\n   - Invalid API key"
                    "\n   - Network connectivity issues"
                )
            )

        self.stdout.write("=" * 70 + "\n")
