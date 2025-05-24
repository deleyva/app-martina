from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.db import transaction

import os

from .models import (
    Student,
    Evaluation,
    PendingEvaluationStatus,
)
from .submission_models import ClassroomSubmission, SubmissionVideo, SubmissionImage
from .submission_forms import ClassroomSubmissionForm, VideoUploadForm, ImageUploadForm
from .tasks import process_video_compression

@login_required
def student_dashboard(request):
    """
    Dashboard view for students showing their evaluations and pending submissions.
    """
    # Get the student profile for the logged-in user
    try:
        student = Student.objects.get(user=request.user)
    except Student.DoesNotExist:
        messages.error(request, "No tienes un perfil de estudiante asociado a tu cuenta.")
        return redirect('home')

    # Get all evaluations for this student
    evaluations = Evaluation.objects.filter(student=student).select_related('evaluation_item')
    
    # Get pending submissions
    pending_statuses = PendingEvaluationStatus.objects.filter(student=student).select_related('evaluation_item')
    
    # Group evaluations by term
    evaluations_by_term = {}
    for evaluation in evaluations:
        term = evaluation.evaluation_item.term or 'Sin periodo'
        if term not in evaluations_by_term:
            evaluations_by_term[term] = []
        evaluations_by_term[term].append(evaluation)
    
    # Check which pending items have submissions
    has_submission = {}
    for status in pending_statuses:
        has_submission[status.id] = hasattr(status, 'submission')
    
    context = {
        'student': student,
        'evaluations_by_term': evaluations_by_term,
        'pending_statuses': pending_statuses,
        'has_submission': has_submission,
    }
    
    return render(request, 'evaluations/student_dashboard.html', context)


@login_required
def create_submission(request, status_id):
    """
    View for initiating a submission for a pending evaluation.
    On GET, it ensures a submission record exists and redirects to the edit view.
    """
    pending_status = get_object_or_404(
        PendingEvaluationStatus, 
        id=status_id,
        student__user=request.user,
        classroom_submission=True
    )
    
    # Try to get an existing submission
    try:
        submission = pending_status.submission
    except ClassroomSubmission.DoesNotExist:
        # If no submission exists, create one
        submission = ClassroomSubmission.objects.create(pending_status=pending_status)
        messages.info(request, "Se ha iniciado tu entrega. Ahora puedes añadir detalles, vídeos e imágenes.")
    
    # Always redirect to the edit view, whether submission was pre-existing or just created
    return redirect('edit_submission', submission_id=submission.id)


@login_required
def edit_submission(request, submission_id):
    """
    View for editing an existing submission and adding videos/images.
    """
    # Get the submission and check ownership
    submission = get_object_or_404(
        ClassroomSubmission, 
        id=submission_id,
        pending_status__student__user=request.user
    )
    
    if request.method == 'POST':
        form = ClassroomSubmissionForm(request.POST, instance=submission)
        if form.is_valid():
            form.save()
            messages.success(request, "Tu entrega ha sido actualizada correctamente.")
            return redirect('edit_submission', submission_id=submission.id)
    else:
        form = ClassroomSubmissionForm(instance=submission)
    
    # Get videos and images
    videos = submission.videos.all()
    images = submission.images.all()
    
    video_form = VideoUploadForm()
    image_form = ImageUploadForm()
    
    context = {
        'form': form,
        'submission': submission,
        'pending_status': submission.pending_status,
        'videos': videos,
        'images': images,
        'video_form': video_form,
        'image_form': image_form,
        # Siempre mostramos las opciones de subida de archivos
        'submission_type': 'edit'
    }
    
    return render(request, 'evaluations/submission_form.html', context)


@login_required
@require_http_methods(["POST"])
def upload_video(request, submission_id):
    """
    View for uploading videos and enqueuing compression task.
    """
    classroom_submission = get_object_or_404(
        ClassroomSubmission, 
        id=submission_id,
        pending_status__student__user=request.user
    )
    
    form = VideoUploadForm(request.POST, request.FILES)
    if form.is_valid():
        video_file = request.FILES['video']
        submission_video = SubmissionVideo.objects.create(
            submission=classroom_submission,
            video=video_file,
            original_filename=video_file.name,
            processing_status='PENDING'
        )

        # Encolar la tarea de compresión DESPUÉS de que la transacción se haya completado
        transaction.on_commit(
            lambda: process_video_compression(submission_video.id)
        )

        messages.success(request, "Vídeo subido correctamente. Se está procesando en segundo plano.")
    else:
        # Construir un mensaje de error más detallado
        error_list = []
        for field, errors in form.errors.items():
            for error in errors:
                error_list.append(f"{form.fields[field].label if field != '__all__' else ''}: {error}")
        error_string = " ".join(error_list)
        messages.error(request, f"Por favor, corrige los errores en el formulario: {error_string}")
    
    return redirect('edit_submission', submission_id=classroom_submission.id)


@login_required
@require_http_methods(["POST"])
def upload_image(request, submission_id):
    """
    View for uploading images.
    """
    submission = get_object_or_404(
        ClassroomSubmission, 
        id=submission_id,
        pending_status__student__user=request.user
    )
    
    form = ImageUploadForm(request.POST, request.FILES)
    if form.is_valid():
        image = form.save(commit=False)
        image.submission = submission
        image.original_filename = request.FILES['image'].name
        image.save()
        
        messages.success(request, "Imagen subida correctamente.")
    else:
        messages.error(request, "Error al subir la imagen.")
    
    return redirect('edit_submission', submission_id=submission.id)


@login_required
@require_http_methods(["POST"])
def delete_video(request, video_id):
    """
    View for deleting videos.
    """
    video = get_object_or_404(
        SubmissionVideo, 
        id=video_id,
        submission__pending_status__student__user=request.user
    )
    
    submission_id = video.submission.id
    
    # Eliminar el archivo físico primero
    if video.video and hasattr(video.video, 'path') and os.path.exists(video.video.path):
        try:
            os.remove(video.video.path)
            messages.success(request, "Archivo de vídeo eliminado del servidor.")
        except Exception as e:
            messages.warning(request, f"No se pudo eliminar el archivo físico: {str(e)}")
    
    # Eliminar el registro de la base de datos
    video.delete()
    
    messages.success(request, "Vídeo eliminado correctamente de la base de datos.")
    return redirect('edit_submission', submission_id=submission_id)


@login_required
@require_http_methods(["POST"])
def delete_image(request, image_id):
    """
    View for deleting images.
    """
    image = get_object_or_404(
        SubmissionImage, 
        id=image_id,
        submission__pending_status__student__user=request.user
    )
    
    submission_id = image.submission.id
    
    # Eliminar el archivo físico primero
    if image.image and hasattr(image.image, 'path') and os.path.exists(image.image.path):
        try:
            os.remove(image.image.path)
            messages.success(request, "Archivo de imagen eliminado del servidor.")
        except Exception as e:
            messages.warning(request, f"No se pudo eliminar el archivo físico: {str(e)}")
    
    # Eliminar el registro de la base de datos
    image.delete()
    
    messages.success(request, "Imagen eliminada correctamente de la base de datos.")
    return redirect('edit_submission', submission_id=submission_id)


# Teacher views for viewing and grading submissions

@login_required
def teacher_view_submission(request, status_id):
    """
    View for teachers to see student submissions.
    """
    if not request.user.is_staff:
        messages.error(request, "No tienes permisos para acceder a esta sección.")
        return redirect('home')
    
    # Get the pending status
    pending_status = get_object_or_404(
        PendingEvaluationStatus, 
        id=status_id,
        classroom_submission=True
    )
    
    # Check if submission exists
    try:
        submission = pending_status.submission
        
        # Get videos and images
        videos = submission.videos.all()
        images = submission.images.all()
        
        context = {
            'pending_status': pending_status,
            'submission': submission,
            'videos': videos,
            'images': images,
        }
        
        return render(request, 'evaluations/teacher_view_submission.html', context)
        
    except ClassroomSubmission.DoesNotExist:
        messages.error(request, "Este estudiante aún no ha realizado ninguna entrega.")
        return redirect('pending_evaluations')
