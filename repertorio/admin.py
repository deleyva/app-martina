"""El admin es donde se corrige lo que viene mal de origen.

La pieza importante está en `save_model`: cualquier campo importado que toques
queda anotado en `Cancion.bloqueados`, y desde ese momento la importación lo
respeta. No hay que marcar nada ni acordarse de nada, que es justo la clase de
disciplina que falla el día que tienes prisa.
"""

from django.contrib import admin, messages
from django.db.models import Q

from repertorio.models import (
    CAMPOS_IMPORTADOS,
    Artista,
    Cancion,
    Genero,
    Idioma,
    Sincronizacion,
    Version,
)


class SinIdentificadorFilter(admin.SimpleListFilter):
    """Para poder ir a por las que no enlazan a ningún sitio y arreglarlas."""

    title = "identificadores que faltan"
    parameter_name = "falta"

    def lookups(self, request, model_admin):
        return [
            ("video", "Sin vídeo"),
            ("spotify", "Sin Spotify"),
            ("cualquiera", "Sin vídeo o sin Spotify"),
            ("slug", "Sin enlace a JamZone"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "video":
            return queryset.filter(youtube_id="")
        if self.value() == "spotify":
            return queryset.filter(spotify_id="")
        if self.value() == "cualquiera":
            return queryset.filter(Q(youtube_id="") | Q(spotify_id=""))
        if self.value() == "slug":
            return queryset.filter(slug_externo="", origen=Cancion.JAMZONE)
        return queryset


class CorregidaFilter(admin.SimpleListFilter):
    title = "corregida a mano"
    parameter_name = "corregida"

    def lookups(self, request, model_admin):
        return [("si", "Sí"), ("no", "No")]

    def queryset(self, request, queryset):
        if self.value() == "si":
            return queryset.exclude(bloqueados=[])
        if self.value() == "no":
            return queryset.filter(bloqueados=[])
        return queryset


class VersionInline(admin.TabularInline):
    model = Version
    extra = 0


@admin.register(Cancion)
class CancionAdmin(admin.ModelAdmin):
    list_display = ("titulo", "anio", "num_acordes", "origen", "favorito", "corregida")
    list_filter = (
        SinIdentificadorFilter,
        CorregidaFilter,
        "origen",
        "favorito",
        "decada",
        "num_acordes",
        "idiomas",
    )
    search_fields = ("titulo", "artistas__nombre", "notas")
    filter_horizontal = ("artistas", "generos", "idiomas")
    inlines = [VersionInline]
    readonly_fields = ("decada", "fuente_id", "bloqueados", "importado_en", "actualizado_en")
    actions = ["soltar_correcciones"]

    @admin.display(description="Corregida", boolean=True)
    def corregida(self, obj):
        return bool(obj.bloqueados)

    def save_model(self, request, obj, form, change):
        """Anota como corregido todo campo importado cuyo valor haya cambiado.

        Compara contra lo que hay en la base y NO usa `form.changed_data`. El
        admin de Django compara los `JSONField` como cadenas de texto, así que
        `changed_data` incluía `forma` cada vez que se abría y guardaba una
        canción sin tocar nada: habría ido congelando campos en silencio.
        """
        nuevos = []
        if change:
            anterior = Cancion.objects.filter(pk=obj.pk).first()
            if anterior is not None:
                cambiados = [
                    campo
                    for campo in CAMPOS_IMPORTADOS
                    if getattr(anterior, campo) != getattr(obj, campo)
                ]
                nuevos = obj.bloquear(cambiados)
        super().save_model(request, obj, form, change)
        if nuevos:
            self.message_user(
                request,
                "A partir de ahora la importación respetará estos campos: "
                + ", ".join(nuevos)
                + ". Usa «Soltar correcciones» si quieres que JamZone vuelva a mandar.",
                messages.INFO,
            )

    @admin.action(description="Soltar correcciones (que vuelva a mandar JamZone)")
    def soltar_correcciones(self, request, queryset):
        afectadas = queryset.exclude(bloqueados=[]).count()
        queryset.update(bloqueados=[])
        self.message_user(
            request,
            f"{afectadas} canción(es) vuelven a aceptar lo que traiga la importación. "
            "Los cambios se aplicarán en la próxima sincronización.",
            messages.SUCCESS,
        )


@admin.register(Sincronizacion)
class SincronizacionAdmin(admin.ModelAdmin):
    list_display = (
        "momento",
        "automatica",
        "recibidas",
        "creadas",
        "actualizadas",
        "campos_respetados",
        "fallos",
    )
    list_filter = ("automatica",)
    readonly_fields = [f.name for f in Sincronizacion._meta.fields]

    def has_add_permission(self, request):
        return False


admin.site.register([Artista, Genero, Idioma])
