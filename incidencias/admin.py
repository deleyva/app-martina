from django.contrib import admin

from .models import Adjunto
from .models import Comentario
from .models import Comunicacion
from .models import Derivacion
from .models import Etiqueta
from .models import GeminiAPIUsage
from .models import Incidencia
from .models import ProcessedEmail
from .models import Servicio
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
    list_display = ("titulo", "ambito", "urgencia", "estado", "ubicacion", "reportero_nombre", "asignado_a", "created_at")
    list_filter = ("estado", "ambito", "urgencia", "ubicacion__planta", "es_privada")
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



@admin.action(description="Regenerar el enlace público")
def regenerar_token(modeladmin, request, queryset):
    for servicio in queryset:
        servicio.regenerar_token()


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "activo", "orden", "correos", "telefono")
    list_filter = ("activo",)
    search_fields = ("nombre", "que_va_aqui", "correos")
    prepopulated_fields = {"slug": ("nombre",)}
    readonly_fields = ("token", "url_publica")
    actions = [regenerar_token]


class ComunicacionInline(admin.TabularInline):
    model = Comunicacion
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Derivacion)
class DerivacionAdmin(admin.ModelAdmin):
    list_display = ("asunto", "servicio", "estado", "resultado", "ticket_externo", "enviada_at", "created_at")
    list_filter = ("estado", "servicio", "resultado")
    search_fields = ("asunto", "cuerpo", "ticket_externo", "incidencia__titulo")
    raw_id_fields = ("incidencia",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [ComunicacionInline]
