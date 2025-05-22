from django.contrib import admin
from .models import (
    Student,
    EvaluationItem,
    Evaluation,
    RubricCategory,
    RubricScore,
    PendingEvaluationStatus,
)
from .submission_models import ClassroomSubmission, SubmissionVideo, SubmissionImage

# Register your models here.


class RubricCategoryInline(admin.StackedInline):
    model = RubricCategory
    extra = 1
    fields = ("name", "description", "max_points", "order")
    ordering = ("order",)
    classes = ["collapse", "open"]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("get_name", "group", "get_pending_count")
    list_filter = ("group",)
    search_fields = ("user__name", "group")

    def get_name(self, obj):
        return obj.user.name if obj.user else f"Student {obj.id}"

    get_name.short_description = "Nombre"

    def get_pending_count(self, obj):
        return obj.pending_statuses.count()

    get_pending_count.short_description = "Evaluaciones pendientes"


@admin.register(EvaluationItem)
class EvaluationItemAdmin(admin.ModelAdmin):
    list_display = ("name", "term", "description", "get_categories_count")
    list_filter = ("term",)
    search_fields = ("name",)
    inlines = [RubricCategoryInline]

    def get_categories_count(self, obj):
        return obj.rubric_categories.count()

    get_categories_count.short_description = "Categorías de rúbrica"


@admin.register(RubricCategory)
class RubricCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "evaluation_item", "max_points", "order")
    list_filter = ("evaluation_item", "max_points")
    search_fields = ("name", "description")
    ordering = ("evaluation_item", "order")
    fields = ("name", "description", "max_points", "order", "evaluation_item")
    list_editable = ("order", "evaluation_item")


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "evaluation_item",
        "score",
        "max_score",
        "classroom_submission",
        "feedback",
        "sent_by_mail",
        "date_evaluated",
    )
    list_filter = ("evaluation_item", "classroom_submission", "max_score")
    search_fields = ("student__user__name",)
    date_hierarchy = None
    readonly_fields = ("date_evaluated",)
    fieldsets = (
        (None, {"fields": ("student", "evaluation_item", "score", "date_evaluated")}),
        (
            "Retroalimentación",
            {
                "fields": ("feedback", "sent_by_mail"),
                "classes": ("wide",),
                "description": "Retroalimentación para el estudiante y estado de envío",
            },
        ),
        (
            "Configuración avanzada",
            {
                "fields": ("max_score", "classroom_submission"),
                "classes": ("collapse",),
                "description": "Configuración de nota máxima y entrega por classroom",
            },
        ),
    )


@admin.register(RubricScore)
class RubricScoreAdmin(admin.ModelAdmin):
    list_display = ("evaluation", "category", "points")
    list_filter = ("category", "points")
    search_fields = ("evaluation__student__user__name", "category__name")


@admin.register(PendingEvaluationStatus)
class PendingEvaluationStatusAdmin(admin.ModelAdmin):
    list_display = ("student", "evaluation_item", "classroom_submission", "feedback", "created_at")
    list_filter = ("evaluation_item", "classroom_submission", "created_at")
    search_fields = ("student__user__name",)
    date_hierarchy = "created_at"


@admin.register(ClassroomSubmission)
class ClassroomSubmissionAdmin(admin.ModelAdmin):
    list_display = ("pending_status", "submitted_at", "updated_at")
    list_filter = ("submitted_at", "updated_at")
    search_fields = ("pending_status__student__user__name",)
    date_hierarchy = "submitted_at"


@admin.register(SubmissionVideo)
class SubmissionVideoAdmin(admin.ModelAdmin):
    list_display = ("submission", "original_filename")
    search_fields = ("submission__pending_status__student__user__name", "original_filename")


@admin.register(SubmissionImage)
class SubmissionImageAdmin(admin.ModelAdmin):
    list_display = ("submission", "original_filename")
    search_fields = ("submission__pending_status__student__user__name", "original_filename")
