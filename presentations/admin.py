from django.contrib import admin
from .models import (
    PresentationTemplate,
    Presentation,
    PresentationSlide,
    PresentationExport,
    PresentationShare,
)

# Register your models here.


class PresentationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_type', 'created_by', 'is_public', 'created_at']
    search_fields = ['name', 'description']
    list_filter = ['template_type', 'is_public', 'theme', 'created_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'template_type', 'created_by', 'is_public')
        }),
        ('Configuración de Diseño', {
            'fields': ('theme', 'page_format', 'orientation')
        }),
        ('Personalización', {
            'fields': ('custom_css',),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es un objeto nuevo
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class PresentationSlideInline(admin.TabularInline):
    model = PresentationSlide
    extra = 1
    fields = ['order', 'title', 'slide_type', 'content_type', 'object_id', 'duration']
    ordering = ['order']


class PresentationAdmin(admin.ModelAdmin):
    list_display = ['title', 'template', 'status', 'created_by', 'generated_at', 'created_at']
    search_fields = ['title', 'description']
    list_filter = ['status', 'template', 'created_at', 'generated_at']
    inlines = [PresentationSlideInline]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'template', 'created_by')
        }),
        ('Contenido Fuente', {
            'fields': ('source_content_type', 'source_object_id')
        }),
        ('Estado y Archivos', {
            'fields': ('status', 'html_file', 'pdf_file', 'generated_at')
        }),
        ('Configuración Personalizada', {
            'fields': ('custom_settings',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['generated_at']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es un objeto nuevo
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class PresentationExportAdmin(admin.ModelAdmin):
    list_display = ['presentation', 'export_type', 'status', 'file_size', 'created_by', 'created_at']
    search_fields = ['presentation__title']
    list_filter = ['export_type', 'status', 'created_at']
    
    fieldsets = (
        (None, {
            'fields': ('presentation', 'export_type', 'created_by')
        }),
        ('Estado', {
            'fields': ('status', 'error_message', 'completed_at')
        }),
        ('Archivo', {
            'fields': ('file', 'file_size')
        }),
        ('Configuración', {
            'fields': ('export_settings',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['file_size', 'completed_at']


class PresentationShareAdmin(admin.ModelAdmin):
    list_display = ['presentation', 'shared_with', 'shared_by', 'permission_level', 'is_active', 'created_at']
    search_fields = ['presentation__title', 'shared_with__username', 'shared_by__username']
    list_filter = ['permission_level', 'is_active', 'created_at', 'expires_at']
    
    fieldsets = (
        (None, {
            'fields': ('presentation', 'shared_with', 'shared_by')
        }),
        ('Permisos', {
            'fields': ('permission_level', 'is_active', 'expires_at')
        }),
        ('Mensaje', {
            'fields': ('message',)
        })
    )


admin.site.register(PresentationTemplate, PresentationTemplateAdmin)
admin.site.register(Presentation, PresentationAdmin)
admin.site.register(PresentationSlide)
admin.site.register(PresentationExport, PresentationExportAdmin)
admin.site.register(PresentationShare, PresentationShareAdmin)
