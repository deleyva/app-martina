from django.contrib import admin
from .models import (
    Student, 
    EvaluationItem, 
    RubricItem, 
    Evaluation, 
    RubricCategory, 
    RubricCriteria,
    RubricScore
)

# Register your models here.

class RubricCriteriaInline(admin.TabularInline):
    model = RubricCriteria
    extra = 3  # Mostrar 3 filas vacías para añadir criterios (0, 1, 2 puntos)
    min_num = 1  # Al menos un criterio
    fields = ('points', 'description')
    ordering = ('-points',)


class RubricCategoryInline(admin.StackedInline):
    model = RubricCategory
    extra = 1
    fields = ('name', 'description', 'max_points', 'order')
    ordering = ('order',)
    classes = ['collapse', 'open']
    

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'group', 'pending_evaluation')
    list_filter = ('group', 'pending_evaluation')
    search_fields = ('first_name', 'last_name', 'group')


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
    list_display = ('name', 'evaluation_item', 'max_points', 'order', 'get_criteria_count')
    list_filter = ('evaluation_item', 'max_points')
    search_fields = ('name', 'description')
    ordering = ('evaluation_item', 'order')
    inlines = [RubricCriteriaInline]
    
    def get_criteria_count(self, obj):
        return obj.criteria.count()
    get_criteria_count.short_description = 'Criterios'


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


@admin.register(RubricCriteria)
class RubricCriteriaAdmin(admin.ModelAdmin):
    list_display = ('category', 'points', 'description')
    list_filter = ('category', 'points')
    search_fields = ('description',)
    ordering = ('category', '-points')


@admin.register(RubricScore)
class RubricScoreAdmin(admin.ModelAdmin):
    list_display = ('evaluation', 'category', 'points')
    list_filter = ('category', 'points')
    search_fields = ('evaluation__student__first_name', 'evaluation__student__last_name', 'category__name')
