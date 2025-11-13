from django.contrib import admin
from .models import (
    Subject,
    Group,
    Student,
    GroupLibraryItem,
    ClassSession,
    ClassSessionItem,
)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "icon", "color", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "description")
    readonly_fields = ("created_at",)
    
    fieldsets = (
        (None, {
            "fields": ("name", "code", "description")
        }),
        ("Presentación", {
            "fields": ("icon", "color")
        }),
        ("Estado", {
            "fields": ("is_active", "created_at")
        }),
    )


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "academic_year", "get_teachers_count", "get_students_count", "created_at")
    list_filter = ("subject", "academic_year", "created_at")
    search_fields = ("name", "teachers__name")
    filter_horizontal = ("teachers",)
    readonly_fields = ("created_at",)
    
    fieldsets = (
        (None, {
            "fields": ("name", "subject", "academic_year")
        }),
        ("Profesores", {
            "fields": ("teachers",)
        }),
        ("Información", {
            "fields": ("created_at",)
        }),
    )
    
    def get_teachers_count(self, obj):
        return obj.teachers.count()
    get_teachers_count.short_description = "Profesores"
    
    def get_students_count(self, obj):
        return obj.students.count()
    get_students_count.short_description = "Estudiantes"


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "get_group_subject")
    list_filter = ("group__subject", "group")
    search_fields = ("user__name", "user__email", "group__name")
    raw_id_fields = ("user",)
    
    def get_group_subject(self, obj):
        return obj.group.subject.name
    get_group_subject.short_description = "Asignatura"


@admin.register(GroupLibraryItem)
class GroupLibraryItemAdmin(admin.ModelAdmin):
    list_display = ("group", "get_content_title", "get_content_type", "added_by", "added_at")
    list_filter = ("group", "content_type", "added_at")
    search_fields = ("group__name", "notes")
    raw_id_fields = ("added_by",)
    readonly_fields = ("added_at", "get_content_title", "get_content_type")
    
    def get_content_title(self, obj):
        return obj.get_content_title()
    get_content_title.short_description = "Contenido"
    
    def get_content_type(self, obj):
        return obj.get_content_type_name()
    get_content_type.short_description = "Tipo"


class ClassSessionItemInline(admin.TabularInline):
    model = ClassSessionItem
    extra = 0
    fields = ("order", "get_content_title", "get_content_type", "notes")
    readonly_fields = ("get_content_title", "get_content_type")
    
    def get_content_title(self, obj):
        return obj.get_content_title()
    get_content_title.short_description = "Contenido"
    
    def get_content_type(self, obj):
        return obj.get_content_type_name()
    get_content_type.short_description = "Tipo"


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "group", "date", "teacher", "get_items_count", "created_at")
    list_filter = ("group", "teacher", "date")
    search_fields = ("title", "group__name", "teacher__name")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "date"
    inlines = [ClassSessionItemInline]
    
    fieldsets = (
        (None, {
            "fields": ("title", "group", "teacher", "date")
        }),
        ("Contenido", {
            "fields": ("notes", "metadata")
        }),
        ("Información", {
            "fields": ("created_at", "updated_at")
        }),
    )
    
    def get_items_count(self, obj):
        return obj.items.count()
    get_items_count.short_description = "Items"


@admin.register(ClassSessionItem)
class ClassSessionItemAdmin(admin.ModelAdmin):
    list_display = ("session", "order", "get_content_title", "get_content_type", "added_at")
    list_filter = ("session__group", "content_type")
    search_fields = ("session__title", "notes")
    readonly_fields = ("added_at", "get_content_title", "get_content_type")
    
    def get_content_title(self, obj):
        return obj.get_content_title()
    get_content_title.short_description = "Contenido"
    
    def get_content_type(self, obj):
        return obj.get_content_type_name()
    get_content_type.short_description = "Tipo"
