from django.contrib import admin

from .models import Adjunto
from .models import Comentario
from .models import Etiqueta
from .models import GeminiAPIUsage
from .models import Incidencia
from .models import ProcessedEmail
from .models import Tecnico
from .models import Ubicacion


@admin.register(Ubicacion)
class UbicacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "grupo", "planta")
    list_filter = ("planta",)
    search_fields = ("nombre", "grupo")


@admin.register(Etiqueta)
class EtiquetaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug")
    prepopulated_fields = {"slug": ("nombre",)}


class ComentarioInline(admin.TabularInline):
    model = Comentario
    extra = 0
    readonly_fields = ("created_at",)


class AdjuntoInline(admin.TabularInline):
    model = Adjunto
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Incidencia)
class IncidenciaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "urgencia", "estado", "ubicacion", "reportero_nombre", "asignado_a", "created_at")
    list_filter = ("estado", "urgencia", "ubicacion__planta", "es_privada")
    search_fields = ("titulo", "descripcion", "reportero_nombre")
    filter_horizontal = ("etiquetas",)
    inlines = [ComentarioInline, AdjuntoInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(Tecnico)
class TecnicoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "user", "activo")
    list_filter = ("activo",)


@admin.register(GeminiAPIUsage)
class GeminiAPIUsageAdmin(admin.ModelAdmin):
    list_display = ("caller", "success", "tokens_used", "timestamp")
    list_filter = ("caller", "success")
    readonly_fields = ("timestamp",)
    date_hierarchy = "timestamp"


@admin.register(ProcessedEmail)
class ProcessedEmailAdmin(admin.ModelAdmin):
    list_display = ("raw_subject", "raw_sender", "incidencia", "skipped", "processed_at")
    list_filter = ("skipped",)
    search_fields = ("raw_subject", "raw_sender", "message_id")
    readonly_fields = ("processed_at",)
    date_hierarchy = "processed_at"
    raw_id_fields = ("incidencia",)

