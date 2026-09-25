from django.contrib import admin

from .models import Elemento
from .models import Libreta


class ElementoInline(admin.TabularInline):
    model = Elemento
    extra = 0
    fields = ("orden", "titulo", "copias", "documento", "imagen", "texto")


@admin.register(Libreta)
class LibretaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "subtitulo", "user", "actualizada")
    search_fields = ("titulo", "subtitulo", "user__email")
    inlines = [ElementoInline]
