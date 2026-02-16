from django.apps import AppConfig


class ContentHubConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "content_hub"
    verbose_name = "Content Hub"

    def ready(self):
        # Import signals when app is ready
        try:
            import content_hub.signals  # noqa: F401
        except ImportError:
            pass
