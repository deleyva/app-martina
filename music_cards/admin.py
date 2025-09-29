from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect, get_object_or_404
from django.template.response import TemplateResponse
from django.utils.html import format_html

from .models import (
    Author,
    Category,
    CategoryItem,
    ContentLibrary,
    Embed,
    File,
    LibraryCollaboration,
    LibraryItem,
    MusicItem,
    Tag,
    Text,
    UserReview,
    UserStudySession,
)


class MusicItemAdmin(admin.ModelAdmin):
    list_display = ["title", "display_tags", "visibility", "created_by", "is_template", "created_at", "updated_at"]
    search_fields = ["title", "created_by__username"]
    list_filter = ["visibility", "is_template", "created_at", "tags"]
    filter_horizontal = ["tags", "texts", "files", "embeds", "shared_with"]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'created_by')
        }),
        ('Contenido', {
            'fields': ('texts', 'files', 'embeds', 'tags')
        }),
        ('Compartir y Visibilidad', {
            'fields': ('visibility', 'shared_with', 'is_template')
        }),
        ('Metadatos', {
            'fields': ('original_item',),
            'classes': ('collapse',)
        })
    )

    def display_tags(self, obj):
        return ", ".join(
            [
                f"{tag.key}{':' + tag.value if tag.value else ''}"
                for tag in obj.tags.all()
            ]
        )

    display_tags.short_description = "Tags"
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es un objeto nuevo
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class CategoryItemInline(admin.TabularInline):
    model = CategoryItem
    extra = 1
    ordering = ["order"]
    fields = ["text", "file", "embed", "order"]


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


class LibraryItemInline(admin.TabularInline):
    model = LibraryItem
    extra = 1
    fields = ['music_item', 'added_by', 'order', 'notes']
    readonly_fields = ['added_by']


class LibraryCollaborationInline(admin.TabularInline):
    model = LibraryCollaboration
    extra = 1
    fields = ['collaborator', 'permission_level']


class ContentLibraryAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'is_public', 'created_at', 'updated_at']
    search_fields = ['name', 'description', 'owner__username']
    list_filter = ['is_public', 'created_at', 'tags']
    filter_horizontal = ['tags']
    inlines = [LibraryCollaborationInline, LibraryItemInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'owner')
        }),
        ('Configuración', {
            'fields': ('is_public', 'tags')
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es un objeto nuevo
            obj.owner = request.user
        super().save_model(request, obj, form, change)


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
admin.site.register(ContentLibrary, ContentLibraryAdmin)
admin.site.register(LibraryCollaboration)
admin.site.register(LibraryItem)
