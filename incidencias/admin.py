from django.contrib import admin

from .models import Adjunto
from .models import Comentario
from .models import Etiqueta
from .models import Incidencia
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
