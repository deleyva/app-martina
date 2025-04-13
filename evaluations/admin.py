from django.contrib import admin
from .models import (
    Student, 
    EvaluationItem, 
    Evaluation, 
    RubricCategory, 
    RubricScore
)

# Register your models here.

class RubricCategoryInline(admin.StackedInline):
    model = RubricCategory
    extra = 1
    fields = ('name', 'description', 'max_points', 'order')
    ordering = ('order',)
    classes = ['collapse', 'open']
    

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('get_name', 'group', 'pending_evaluation')
    list_filter = ('group', 'pending_evaluation')
    search_fields = ('user__name', 'group')
    
    def get_name(self, obj):
        return obj.user.name if obj.user else f"Student {obj.id}"
    get_name.short_description = 'Nombre'


@admin.register(EvaluationItem)
class EvaluationItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'term', 'description', 'get_categories_count')
    list_filter = ('term',)
    search_fields = ('name',)
    inlines = [RubricCategoryInline]
    
    def get_categories_count(self, obj):
        return obj.rubric_categories.count()
    get_categories_count.short_description = 'Categorías de rúbrica'


@admin.register(RubricCategory)
class RubricCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'evaluation_item', 'max_points', 'order')
    list_filter = ('evaluation_item', 'max_points')
    search_fields = ('name', 'description')
    ordering = ('evaluation_item', 'order')
    fields = ('name', 'description', 'max_points', 'order', 'evaluation_item')
    list_editable = ('order', 'evaluation_item')


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('student', 'evaluation_item', 'score', 'date_evaluated')
    list_filter = ('evaluation_item', 'date_evaluated')
    search_fields = ('student__user__name',)
    date_hierarchy = 'date_evaluated'


@admin.register(RubricScore)
class RubricScoreAdmin(admin.ModelAdmin):
    list_display = ('evaluation', 'category', 'points')
    list_filter = ('category', 'points')
    search_fields = ('evaluation__student__user__name', 'category__name')
