from django.contrib import admin
from .models import LibraryItem, ReviewLog


@admin.register(LibraryItem)
class LibraryItemAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "get_content_title",
        "get_content_type_name",
        "added_at",
        "times_viewed",
        "favorite",
    ]
    list_filter = ["content_type", "added_at", "favorite", "user"]
    # user__username no existe en este proyecto: rompía la búsqueda del admin
    search_fields = ["user__email", "notes"]
    readonly_fields = ["content_type", "object_id", "added_at", "last_viewed"]
    date_hierarchy = "added_at"


@admin.register(ReviewLog)
class ReviewLogAdmin(admin.ModelAdmin):
    """Histórico en solo lectura: los repasos se insertan, no se editan."""

    list_display = [
        "reviewed_at",
        "user",
        "item",
        "source",
        "proficiency_before",
        "proficiency_after",
        "duration_seconds",
        "deck",
    ]
    list_filter = ["source", "reviewed_at", "user", "deck"]
    search_fields = ["user__email"]
    date_hierarchy = "reviewed_at"
    list_select_related = ["user", "item", "deck"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
