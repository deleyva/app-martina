from django.db import models
from django.conf import settings
import os
import uuid
from .models import Student, EvaluationItem, PendingEvaluationStatus


def submission_video_path(instance, filename):
    """Generate a unique path for uploaded videos."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('submissions', 'videos', filename)


def submission_image_path(instance, filename):
    """Generate a unique path for uploaded images."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('submissions', 'images', filename)


class ClassroomSubmission(models.Model):
    """Model to store submissions from students for classroom evaluations."""
    pending_status = models.OneToOneField(
        PendingEvaluationStatus, 
        on_delete=models.CASCADE,
        related_name="submission"
    )
    notes = models.TextField(blank=True, verbose_name="Notas adicionales")
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Submission for {self.pending_status.student} - {self.pending_status.evaluation_item}"

    class Meta:
        verbose_name = "Entrega de Classroom"
        verbose_name_plural = "Entregas de Classroom"


class SubmissionVideo(models.Model):
    """Videos submitted by the student."""
    submission = models.ForeignKey(
        ClassroomSubmission,
        on_delete=models.CASCADE,
        related_name="videos"
    )
    video = models.FileField(
        upload_to=submission_video_path,
        verbose_name="Vídeo"
    )
    original_filename = models.CharField(max_length=255, blank=True)
    
    def __str__(self):
        return f"Video for {self.submission}"


class SubmissionImage(models.Model):
    """Images submitted by the student."""
    submission = models.ForeignKey(
        ClassroomSubmission,
        on_delete=models.CASCADE,
        related_name="images"
    )
    image = models.ImageField(
        upload_to=submission_image_path,
        verbose_name="Imagen"
    )
    original_filename = models.CharField(max_length=255, blank=True)
    
    def __str__(self):
        return f"Image for {self.submission}"
