from django.contrib import admin

from .models import DispositivoWifi


@admin.register(DispositivoWifi)
class DispositivoWifiAdmin(admin.ModelAdmin):
    list_display = ("mac", "usuario", "descripcion", "estado", "created_at", "notificado_at")
    list_filter = ("estado", "created_at")
    search_fields = ("mac", "descripcion", "usuario__email", "usuario__name")
    readonly_fields = ("created_at", "updated_at", "anadida_at", "baja_at", "notificado_at")
    autocomplete_fields = ()
    date_hierarchy = "created_at"
