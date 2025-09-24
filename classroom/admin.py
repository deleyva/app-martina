from django.contrib import admin
from .models import (
    Course,
    Enrollment,
    ClassSession,
    SessionContent,
    Assignment,
    AssignmentItem,
    StudentAssignment,
    StudentContribution,
)

# Register your models here.


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1
    fields = ['student', 'is_active', 'enrollment_date', 'notes']
    readonly_fields = ['enrollment_date']


class CourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'teacher', 'academic_year', 'is_active', 'created_at']
    search_fields = ['name', 'teacher__username', 'academic_year']
    list_filter = ['is_active', 'academic_year', 'created_at']
    inlines = [EnrollmentInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'teacher')
        }),
        ('Configuración Académica', {
            'fields': ('academic_year', 'start_date', 'end_date', 'is_active')
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es un objeto nuevo
            obj.teacher = request.user
        super().save_model(request, obj, form, change)


class SessionContentInline(admin.TabularInline):
    model = SessionContent
    extra = 1
    fields = ['music_item', 'order', 'estimated_duration', 'notes']


class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'date', 'start_time', 'status', 'created_at']
    search_fields = ['title', 'course__name']
    list_filter = ['status', 'date', 'course']
    inlines = [SessionContentInline]
    
    fieldsets = (
        (None, {
            'fields': ('course', 'title', 'description')
        }),
        ('Programación', {
            'fields': ('date', 'start_time', 'end_time', 'status')
        })
    )


class AssignmentItemInline(admin.TabularInline):
    model = AssignmentItem
    extra = 1
    fields = ['music_item', 'order', 'instructions']


class StudentAssignmentInline(admin.TabularInline):
    model = StudentAssignment
    extra = 0
    fields = ['student', 'status', 'grade', 'teacher_feedback']
    readonly_fields = ['student']


class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'class_session', 'due_date', 'is_mandatory', 'created_at']
    search_fields = ['title', 'class_session__title', 'class_session__course__name']
    list_filter = ['is_mandatory', 'due_date', 'created_at']
    inlines = [AssignmentItemInline, StudentAssignmentInline]
    
    fieldsets = (
        (None, {
            'fields': ('class_session', 'title', 'description')
        }),
        ('Configuración', {
            'fields': ('due_date', 'is_mandatory', 'allow_late_submission')
        })
    )


class StudentContributionAdmin(admin.ModelAdmin):
    list_display = ['title', 'student', 'course', 'status', 'created_at']
    search_fields = ['title', 'student__username', 'course__name']
    list_filter = ['status', 'approved_for_library', 'created_at']
    
    fieldsets = (
        (None, {
            'fields': ('student', 'course', 'title', 'description')
        }),
        ('Contenido', {
            'fields': ('content_type', 'object_id')
        }),
        ('Moderación', {
            'fields': ('status', 'teacher_feedback', 'approved_by', 'approved_for_library')
        }),
        ('Fechas', {
            'fields': ('submitted_at', 'reviewed_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['submitted_at', 'reviewed_at']


admin.site.register(Course, CourseAdmin)
admin.site.register(Enrollment)
admin.site.register(ClassSession, ClassSessionAdmin)
admin.site.register(SessionContent)
admin.site.register(Assignment, AssignmentAdmin)
admin.site.register(AssignmentItem)
admin.site.register(StudentAssignment)
admin.site.register(StudentContribution, StudentContributionAdmin)
