from django.contrib import admin

from .models import (
    CambioNota,
    Criterio,
    Evidencia,
    Instrumento,
    MarcoEvaluacion,
    Nota,
    NotaManual,
    Plan,
    Prueba,
    Reparto,
)


class CriterioInline(admin.TabularInline):
    model = Criterio
    extra = 0
    fields = ["orden", "codigo", "competencia", "peso", "descripcion"]


@admin.register(MarcoEvaluacion)
class MarcoEvaluacionAdmin(admin.ModelAdmin):
    list_display = ["__str__", "academic_year", "peso_total"]
    list_filter = ["academic_year", "subject"]
    inlines = [CriterioInline]


class RepartoInline(admin.TabularInline):
    model = Reparto
    extra = 0


class PruebaInline(admin.TabularInline):
    model = Prueba
    extra = 0


@admin.register(Instrumento)
class InstrumentoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "plan", "peso", "escala", "agregacion"]
    list_filter = ["plan"]
    inlines = [RepartoInline, PruebaInline]


class InstrumentoInline(admin.TabularInline):
    model = Instrumento
    extra = 0
    fields = ["orden", "nombre", "abreviatura", "escala", "agregacion"]
    show_change_link = True


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["nombre", "marco", "trimestre"]
    list_filter = ["marco", "trimestre"]
    filter_horizontal = ["groups"]
    inlines = [InstrumentoInline]


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    list_display = ["alumno", "prueba", "valor", "updated_by", "updated_at"]
    list_filter = ["prueba__instrumento__plan"]
    search_fields = ["alumno__email", "alumno__name"]
    raw_id_fields = ["alumno", "prueba"]


@admin.register(Evidencia)
class EvidenciaAdmin(admin.ModelAdmin):
    list_display = ["alumno", "prueba", "tipo", "estado", "created_at"]
    list_filter = ["tipo", "estado"]
    raw_id_fields = ["alumno", "prueba"]


@admin.register(NotaManual)
class NotaManualAdmin(admin.ModelAdmin):
    list_display = ["alumno", "group", "ambito", "calificacion", "updated_at"]
    raw_id_fields = ["alumno"]


@admin.register(CambioNota)
class CambioNotaAdmin(admin.ModelAdmin):
    list_display = ["nota", "antes", "despues", "user", "ts"]
    raw_id_fields = ["nota", "revertido_de"]
