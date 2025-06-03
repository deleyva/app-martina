from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
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
    list_display = ("name", "term", "description", "force_web_submission", "classroom_reduces_points", "get_categories_count")
    list_filter = ("term", "force_web_submission", "classroom_reduces_points")
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
    list_display = (
        'id',
        'get_student_identifier',
        'original_filename',
        'processing_status',
        'get_compressed_video_link',
        'get_submission_submitted_at',
    )
    list_filter = (
        'processing_status',
        'submission__pending_status__student__group',
        'submission__pending_status__evaluation_item',
    )
    search_fields = (
        'submission__pending_status__student__user__username',
        'submission__pending_status__student__user__first_name',
        'submission__pending_status__student__user__last_name',
        'submission__pending_status__student__user__email',
        'original_filename',
        'video_file',
    )
    readonly_fields = (
        'id',
        'submission_link',
        'video_file_preview',
        'compressed_video_preview',
        'processing_error',
        'get_submission_submitted_at',
        'get_submission_updated_at',
    )
    list_per_page = 20
    ordering = ('-submission__submitted_at',)

    def get_student_identifier(self, obj):
        # obj is SubmissionVideo
        if not obj.submission:
            return "N/A" # SubmissionVideo has no associated ClassroomSubmission
        
        classroom_submission = obj.submission
        if not classroom_submission.pending_status:
            return "N/A" # ClassroomSubmission has no associated PendingEvaluationStatus
            
        pending_status = classroom_submission.pending_status
        if not pending_status.student:
            return "N/A" # PendingEvaluationStatus has no associated Student
            
        student = pending_status.student
        if student.user:
            # Try to get full name, then username
            full_name = student.user.get_full_name()
            if full_name:
                return full_name
            if student.user.username:
                return student.user.username
            # Fallback if user exists but has no name/username
            return f"User ID: {student.user.id}" 
        else:
            # Student exists but is not linked to a User account
            return f"Student ID: {student.id}"
    get_student_identifier.short_description = 'Estudiante'
    get_student_identifier.admin_order_field = 'submission__pending_status__student__user__last_name'

    def get_submission_submitted_at(self, obj):
        if obj.submission:
            return obj.submission.submitted_at
        return None
    get_submission_submitted_at.admin_order_field = 'submission__submitted_at'
    get_submission_submitted_at.short_description = 'Fecha de Entrega (Submission)'

    def get_submission_updated_at(self, obj):
        if obj.submission:
            return obj.submission.updated_at
        return None
    get_submission_updated_at.admin_order_field = 'submission__updated_at'
    get_submission_updated_at.short_description = 'Última Actualización (Submission)'

    def get_compressed_video_link(self, obj):
        if obj.compressed_video and hasattr(obj.compressed_video, 'url'):
            return format_html("<a href='{url}' target='_blank'>{filename}</a>", 
                               url=obj.compressed_video.url, 
                               filename=obj.compressed_video.name.split('/')[-1])
        elif obj.compressed_video:
            return obj.compressed_video.name.split('/')[-1]
        return "-"
    get_compressed_video_link.short_description = 'Vídeo Comprimido'
    get_compressed_video_link.admin_order_field = 'compressed_video'

    def submission_link(self, obj):
        if obj.submission:
            link = reverse("admin:evaluations_classroomsubmission_change", args=[obj.submission.id])
            return format_html('<a href="{}">{}</a>', link, obj.submission)
        return "N/A"
    submission_link.short_description = 'Entrega Asociada'

    def _video_preview_html(self, video_field):
        if video_field and hasattr(video_field, 'url'):
            filename = video_field.name.split('/')[-1]
            return format_html(
                "<a href='{url}' target='_blank'>{filename}</a><br>"
                "<video width='320' height='240' controls preload='metadata'>"
                "<source src='{url}#t=0.1' type='video/mp4'>"
                "Tu navegador no soporta la etiqueta de vídeo.</video>",
                url=video_field.url,
                filename=filename
            )
        return "No disponible"

    def video_file_preview(self, obj):
        return self._video_preview_html(obj.video_file)
    video_file_preview.short_description = 'Previsualización Vídeo Original'

    def compressed_video_preview(self, obj):
        if obj.processing_status == SubmissionVideo.ProcessingStatus.PROCESSING:
            return "Procesando..."
        elif obj.processing_status == SubmissionVideo.ProcessingStatus.PENDING:
            return "Pendiente de procesamiento"
        elif obj.processing_status == SubmissionVideo.ProcessingStatus.FAILED:
            return format_html("<strong>Fallido:</strong> {}<br>No hay previsualización disponible.", obj.processing_error or 'Error desconocido')
        elif obj.processing_status == SubmissionVideo.ProcessingStatus.COMPLETED and obj.compressed_video:
            return self._video_preview_html(obj.compressed_video)
        return "No disponible o no procesado"
    compressed_video_preview.short_description = 'Previsualización Vídeo Comprimido'


@admin.register(SubmissionImage)
class SubmissionImageAdmin(admin.ModelAdmin):
    list_display = ("submission", "original_filename")
    search_fields = ("submission__pending_status__student__user__name", "original_filename")
