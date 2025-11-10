from django.contrib import admin
from .models import LibraryItem


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
    search_fields = ["user__username", "notes"]
    readonly_fields = ["content_type", "object_id", "added_at", "last_viewed"]
    date_hierarchy = "added_at"
