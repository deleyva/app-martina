from django.contrib import admin
from .models import APIKey

# Register your models here.

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'key', 'created_at', 'is_active', 'last_used')
    list_filter = ('is_active', 'created_at', 'user')
    search_fields = ('name', 'user__email')
    readonly_fields = ('key', 'created_at', 'last_used')
    fieldsets = (
        (None, {
            'fields': ('name', 'user', 'is_active')
        }),
        ('Información', {
            'fields': ('key', 'created_at', 'last_used'),
            'classes': ('collapse',),
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Hacer que el campo key sea de solo lectura solo cuando se edita un objeto existente"""
        return self.readonly_fields if obj else ('created_at', 'last_used')
