from django.apps import AppConfig


class ProgramacionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "programacion"
    verbose_name = "Programación didáctica"

    def ready(self):
        from . import signals  # noqa: F401
