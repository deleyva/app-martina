from django.apps import AppConfig


class MyLibraryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "my_library"

    def ready(self):
        # Las señales que recolocan el orden cuando un libro cambia.
        import my_library.signals  # noqa: F401
