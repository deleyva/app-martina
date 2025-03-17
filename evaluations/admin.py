from django.contrib import admin
from .models import Student, EvaluationItem, RubricItem, Evaluation

# Register your models here.

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'group', 'pending_evaluation')
    list_filter = ('group', 'pending_evaluation')
    search_fields = ('first_name', 'last_name', 'group')

@admin.register(EvaluationItem)
class EvaluationItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(RubricItem)
class RubricItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    ordering = ('order',)

@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('student', 'evaluation_item', 'score', 'date_evaluated')
    list_filter = ('evaluation_item', 'date_evaluated')
    search_fields = ('student__first_name', 'student__last_name')
    date_hierarchy = 'date_evaluated'
