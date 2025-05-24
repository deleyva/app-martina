from django.db import models
import os
import uuid
from .models import PendingEvaluationStatus


def submission_video_path(instance, filename):
    """Generate a unique path for uploaded videos."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('submissions', 'videos', filename)

def submission_compressed_video_path(instance, filename):
    """Generate a unique path for uploaded compressed videos."""
    _, ext = os.path.splitext(filename)
    filename = f"{uuid.uuid4()}_compressed{ext}"
    return os.path.join('submissions', 'videos', 'compressed', filename)


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
    video = models.FileField( # Este será el vídeo original
        upload_to=submission_video_path,
        verbose_name="Vídeo Original"
    )
    original_filename = models.CharField(max_length=255, blank=True)

    # Campos para la compresión
    compressed_video = models.FileField(
        upload_to=submission_compressed_video_path, # Nueva función de path
        verbose_name="Vídeo Comprimido",
        null=True,
        blank=True
    )
    
    PROCESSING_STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('PROCESSING', 'Procesando'),
        ('COMPLETED', 'Completado'),
        ('FAILED', 'Fallido'),
    ]
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS_CHOICES,
        default='PENDING',
        verbose_name="Estado de Procesamiento"
    )
    processing_error = models.TextField(null=True, blank=True, verbose_name="Error de Procesamiento")
    
    def __str__(self):
        status_display = self.get_processing_status_display() if hasattr(self, 'get_processing_status_display') else self.processing_status
        return f"Video for {self.submission} ({status_display}) - Orig: {self.original_filename or 'N/A'}"

    def delete(self, *args, **kwargs):
        # Guardar las rutas de los archivos antes de que el objeto se elimine de la BD
        video_path = None
        if self.video and hasattr(self.video, 'path'):
            video_path = self.video.path

        compressed_video_path = None
        if self.compressed_video and hasattr(self.compressed_video, 'path'):
            compressed_video_path = self.compressed_video.path

        # Eliminar el objeto de la base de datos
        super().delete(*args, **kwargs)

        # Eliminar los archivos del sistema de ficheros
        if video_path:
            if os.path.exists(video_path):
                try:
                    os.remove(video_path)
                    # Opcional: logger.info(f"Successfully deleted original video file: {video_path}")
                except OSError:
                    # Opcional: logger.error(f"Error deleting original video file {video_path}: {e.strerror}")
                    pass # O decidir cómo manejar el error

        if compressed_video_path:
            if os.path.exists(compressed_video_path):
                try:
                    os.remove(compressed_video_path)
                    # Opcional: logger.info(f"Successfully deleted compressed video file: {compressed_video_path}")
                except OSError:
                    # Opcional: logger.error(f"Error deleting compressed video file {compressed_video_path}: {e.strerror}")
                    pass # O decidir cómo manejar el error


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
