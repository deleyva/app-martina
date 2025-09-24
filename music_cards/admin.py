from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect, get_object_or_404
from django.template.response import TemplateResponse  # Añade esta línea
from django.utils.html import format_html
from django.contrib.contenttypes.models import ContentType

from .models import (
    Author,
    Category,
    CategoryItem,
    Embed,
    File,
    MusicItem,
    Tag,
    Text,
    UserReview,
    UserStudySession,
)


class MusicItemAdmin(admin.ModelAdmin):
    list_display = ["title", "display_tags", "created_at", "updated_at"]
    search_fields = ["title"]
    filter_horizontal = ["tags", "texts", "files", "embeds"]

    def display_tags(self, obj):
        return ", ".join(
            [
                f"{tag.key}{':' + tag.value if tag.value else ''}"
                for tag in obj.tags.all()
            ]
        )

    display_tags.short_description = "Tags"


class CategoryItemInline(admin.TabularInline):
    model = CategoryItem
    extra = 1
    ordering = ["order"]
    fields = ["text", "file", "embed", "music_item", "order"]


class CategoryInline(admin.TabularInline):
    model = CategoryItem
    extra = 1
    fields = ["category", "order"]
    verbose_name = "Categoría"
    verbose_name_plural = "Categorías Asociadas"


class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "parent",
        "order",
        "get_full_category_name",
        "created_at",
        "add_subcategory_link",
    )
    search_fields = ("name",)
    list_filter = ("parent",)
    ordering = ["parent", "order"]
    list_editable = ("order",)
    inlines = [CategoryItemInline]

    def add_subcategory_link(self, obj):
        return format_html(
            '<a class="button" href="{}">Añadir Subcategoría</a>',
            f"add_subcategory/{obj.pk}/",
        )

    add_subcategory_link.short_description = "Añadir Subcategoría"
    add_subcategory_link.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "add_subcategory/<int:parent_id>/",
                self.admin_site.admin_view(self.add_subcategory),
                name="add_subcategory",
            ),
        ]
        return custom_urls + urls

    def add_subcategory(self, request, parent_id):
        parent = get_object_or_404(Category, pk=parent_id)
        if request.method == "POST":
            form = self.get_form(request)(request.POST)
            if form.is_valid():
                subcategory = form.save(commit=False)
                subcategory.parent = parent
                subcategory.save()
                self.message_user(
                    request, f"Subcategoría '{subcategory.name}' añadida exitosamente."
                )
                return redirect("admin:music_cards_category_changelist")
        else:
            form = self.get_form(request)(initial={"parent": parent})

        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "parent": parent,
        }

        return TemplateResponse(
            request, "music_cards/admin/add_subcategory.html", context
        )


class TextAdmin(admin.ModelAdmin):
    list_display = ["name", "id", "created_at", "updated_at"]
    search_fields = ["name"]
    list_filter = ["created_at"]
    inlines = [CategoryInline]


class EmbedAdmin(admin.ModelAdmin):
    list_display = ["name", "id", "created_at", "updated_at"]
    search_fields = ["name"]
    list_filter = ["created_at"]
    inlines = [CategoryInline]


class FileAdmin(admin.ModelAdmin):
    list_display = ["name", "id", "created_at", "updated_at"]
    search_fields = ["name"]
    list_filter = ["created_at"]
    inlines = [CategoryInline]


admin.site.register(Author)
admin.site.register(Tag)
admin.site.register(Category, CategoryAdmin)
admin.site.register(CategoryItem)
admin.site.register(MusicItem, MusicItemAdmin)
admin.site.register(Embed, EmbedAdmin)
admin.site.register(File, FileAdmin)
admin.site.register(Text, TextAdmin)
admin.site.register(UserReview)
admin.site.register(UserStudySession)
