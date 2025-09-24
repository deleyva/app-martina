from django.contrib import admin
from .models import (
    StudyContext,
    UniversalStudyItem,
    StudySession,
    StudyParticipation,
    SessionItem,
    StudyProgress,
)

# Register your models here.


class StudyContextAdmin(admin.ModelAdmin):
    list_display = ['name', 'context_type', 'course', 'created_by', 'created_at']
    search_fields = ['name', 'description']
    list_filter = ['context_type', 'created_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'context_type', 'course', 'created_by')
        }),
        ('Configuración de Repetición Espaciada', {
            'fields': ('initial_interval', 'max_interval'),
            'classes': ('collapse',)
        })
    )


class UniversalStudyItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'content_type', 'difficulty_level', 'created_by', 'created_at']
    search_fields = ['title']
    list_filter = ['difficulty_level', 'content_type', 'created_at']
    filter_horizontal = ['tags']
    
    fieldsets = (
        (None, {
            'fields': ('title', 'created_by')
        }),
        ('Contenido Referenciado', {
            'fields': ('content_type', 'object_id')
        }),
        ('Metadatos de Estudio', {
            'fields': ('difficulty_level', 'estimated_practice_time', 'tags')
        })
    )


class StudyParticipationInline(admin.TabularInline):
    model = StudyParticipation
    extra = 1
    fields = ['participant', 'role', 'items_completed', 'total_practice_time']


class SessionItemInline(admin.TabularInline):
    model = SessionItem
    extra = 1
    fields = ['study_item', 'order', 'status', 'time_spent']


class StudySessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'context', 'status', 'scheduled_start', 'created_at']
    search_fields = ['title', 'description']
    list_filter = ['status', 'context', 'scheduled_start', 'created_at']
    inlines = [StudyParticipationInline, SessionItemInline]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'context', 'status')
        }),
        ('Programación', {
            'fields': ('scheduled_start', 'actual_start', 'actual_end')
        })
    )
    
    readonly_fields = ['actual_start', 'actual_end']


class StudyProgressAdmin(admin.ModelAdmin):
    list_display = ['participant', 'study_item', 'context', 'mastery_level', 'practice_count', 'next_review_date']
    search_fields = ['participant__username', 'study_item__title']
    list_filter = ['mastery_level', 'context', 'next_review_date', 'last_practiced']
    
    fieldsets = (
        (None, {
            'fields': ('participant', 'study_item', 'context')
        }),
        ('Progreso', {
            'fields': ('mastery_level', 'practice_count', 'total_practice_time')
        }),
        ('Algoritmo de Repetición Espaciada', {
            'fields': ('current_interval', 'ease_factor', 'next_review_date'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['last_practiced']


admin.site.register(StudyContext, StudyContextAdmin)
admin.site.register(UniversalStudyItem, UniversalStudyItemAdmin)
admin.site.register(StudySession, StudySessionAdmin)
admin.site.register(StudyParticipation)
admin.site.register(SessionItem)
admin.site.register(StudyProgress, StudyProgressAdmin)
