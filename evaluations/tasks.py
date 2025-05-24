from huey.contrib.djhuey import db_task
from django.core.files.base import File
from .submission_models import SubmissionVideo # Asegúrate que la importación sea correcta
import subprocess
import os
import tempfile
import logging
import uuid # Importar uuid

logger = logging.getLogger(__name__)

@db_task()
def process_video_compression(submission_video_id):
    logger.info("Starting video compression for SubmissionVideo ID: %s", submission_video_id)
    video_instance = None # Inicializar para el bloque finally
    compressed_temp_path = None # Inicializar para el bloque finally

    try:
        video_instance = SubmissionVideo.objects.get(pk=submission_video_id)
        video_instance.processing_status = 'PROCESSING'
        video_instance.processing_error = None # Limpiar errores previos
        video_instance.save(update_fields=['processing_status', 'processing_error'])

        original_file_path = video_instance.video.path
        original_filename = os.path.basename(video_instance.video.name)
        
        temp_dir = tempfile.gettempdir()
        base, ext = os.path.splitext(original_filename)
        safe_base = "".join(c if c.isalnum() else '_' for c in base)[:50]
        temp_output_filename = f"huey_temp_{safe_base}_{uuid.uuid4().hex[:8]}{ext}"
        compressed_temp_path = os.path.join(temp_dir, temp_output_filename)

        logger.info("Original file: %s", original_file_path)
        logger.info("Temporary compressed file: %s", compressed_temp_path)

        ffmpeg_command = [
            'ffmpeg',
            '-i', original_file_path,
            '-y',
            '-vf', 'scale=-2:720',
            '-r', '30',
            '-c:v', 'libx264',
            '-preset', 'slow',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-movflags', '+faststart',
            compressed_temp_path
        ]

        logger.info("Executing FFmpeg command: %s", ' '.join(ffmpeg_command))
        result = subprocess.run(ffmpeg_command, check=False, capture_output=True, text=True, encoding='utf-8')

        if result.returncode != 0:
            error_message = f"FFmpeg failed with code {result.returncode}. Stdout: {result.stdout}. Stderr: {result.stderr}"
            logger.error("FFmpeg error: %s", error_message)
            video_instance.processing_status = 'FAILED'
            video_instance.processing_error = error_message
            video_instance.save(update_fields=['processing_status', 'processing_error'])
            return

        logger.info("FFmpeg completed successfully. Stdout: %s", result.stdout)
        if result.stderr:
            logger.warning("FFmpeg Stderr (aunque exitoso): %s", result.stderr)

        with open(compressed_temp_path, 'rb') as f:
            compressed_filename = f"{os.path.splitext(original_filename)[0]}_compressed{os.path.splitext(original_filename)[1]}"
            video_instance.compressed_video.save(
                compressed_filename,
                File(f),
                save=False
            )
        
        video_instance.processing_status = 'COMPLETED'
        video_instance.processing_error = None
        video_instance.save(update_fields=['compressed_video', 'processing_status', 'processing_error'])
        logger.info("Video compression completed and saved for SubmissionVideo ID: %s", submission_video_id)

        # Borrar el vídeo original después de una compresión exitosa
        if video_instance.video and hasattr(video_instance.video, 'path'):
            original_video_path = video_instance.video.path
            if os.path.exists(original_video_path):
                try:
                    os.remove(original_video_path)
                    logger.info("Successfully deleted original video file: %s", original_video_path)
                    # Marcar el campo del archivo original como vacío en el modelo
                    video_instance.video.delete(save=False) # No guarda el modelo inmediatamente
                    video_instance.save(update_fields=['video']) # Guarda solo el campo actualizado
                    logger.info("Original video field cleared for SubmissionVideo ID: %s", submission_video_id)
                except OSError as e:
                    logger.error("Error deleting original video file %s: %s", original_video_path, e.strerror)
            else:
                logger.warning("Original video file not found at path %s, cannot delete.", original_video_path)
        else:
            logger.info("No original video file associated with SubmissionVideo ID: %s to delete.", submission_video_id)

    except SubmissionVideo.DoesNotExist:
        logger.error("SubmissionVideo with ID %s not found.", submission_video_id)
    except Exception as e:
        error_msg = f"Error during video compression for SubmissionVideo ID {submission_video_id}: {str(e)}"
        logger.exception(error_msg)
        if video_instance:
            video_instance.processing_status = 'FAILED'
            video_instance.processing_error = error_msg
            video_instance.save(update_fields=['processing_status', 'processing_error'])
    finally:
        if compressed_temp_path and os.path.exists(compressed_temp_path):
            try:
                os.remove(compressed_temp_path)
                logger.info("Successfully removed temporary file: %s", compressed_temp_path)
            except OSError as e:
                logger.error("Error removing temporary file %s: %s", compressed_temp_path, e.strerror)
