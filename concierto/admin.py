from django.contrib import admin

from .models import Acto
from .models import Tarea
from .models import Voluntario


class VoluntarioInline(admin.TabularInline):
    model = Voluntario
    extra = 0


@admin.register(Acto)
class ActoAdmin(admin.ModelAdmin):
    list_display = ("orden", "artistas", "duracion_minutos")
    ordering = ("orden",)


@admin.register(Tarea)
class TareaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "max_voluntarios", "acto")
    inlines = [VoluntarioInline]


@admin.register(Voluntario)
class VoluntarioAdmin(admin.ModelAdmin):
    list_display = ("username", "tarea", "fecha_registro")
