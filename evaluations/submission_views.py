from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, FormView, CreateView, UpdateView, ListView

import os
import subprocess
import tempfile
from pathlib import Path

from .models import (
    Student,
    EvaluationItem,
    Evaluation,
    PendingEvaluationStatus,
)
from .submission_models import ClassroomSubmission, SubmissionVideo, SubmissionImage
from .submission_forms import ClassroomSubmissionForm, VideoUploadForm, ImageUploadForm


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
    View for creating a new submission for a pending evaluation.
    """
    # Get the pending status
    pending_status = get_object_or_404(
        PendingEvaluationStatus, 
        id=status_id,
        student__user=request.user,
        classroom_submission=True
    )
    
    # Check if submission already exists
    try:
        submission = pending_status.submission
        return redirect('edit_submission', submission_id=submission.id)
    except ClassroomSubmission.DoesNotExist:
        pass
    
    if request.method == 'POST':
        form = ClassroomSubmissionForm(request.POST)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.pending_status = pending_status
            submission.save()
            
            messages.success(request, "Tu entrega ha sido creada. Ahora puedes agregar vídeos e imágenes.")
            return redirect('edit_submission', submission_id=submission.id)
    else:
        form = ClassroomSubmissionForm()
    
    context = {
        'form': form,
        'pending_status': pending_status,
        'submission_type': 'create'
    }
    
    return render(request, 'evaluations/submission_form.html', context)


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
        'submission_type': 'edit'
    }
    
    return render(request, 'evaluations/submission_form.html', context)


@login_required
@require_http_methods(["POST"])
def upload_video(request, submission_id):
    """
    View for uploading and compressing videos.
    """
    submission = get_object_or_404(
        ClassroomSubmission, 
        id=submission_id,
        pending_status__student__user=request.user
    )
    
    form = VideoUploadForm(request.POST, request.FILES)
    if form.is_valid():
        # Get the uploaded video
        uploaded_video = request.FILES['video']
        original_filename = uploaded_video.name
        
        # Create a temporary file for the uploaded video
        with tempfile.NamedTemporaryFile(suffix='.' + original_filename.split('.')[-1], delete=False) as temp_input:
            for chunk in uploaded_video.chunks():
                temp_input.write(chunk)
            temp_input_path = temp_input.name
        
        # Create a temporary file for the compressed output
        temp_output_fd, temp_output_path = tempfile.mkstemp(suffix='.mp4')
        os.close(temp_output_fd)
        
        try:
            # Compress the video using FFmpeg
            compress_cmd = [
                'ffmpeg', '-i', temp_input_path,
                '-vcodec', 'libx264',
                '-crf', '28',  # Compression quality (lower is better, but larger)
                '-preset', 'medium',  # Compression speed vs efficiency trade-off
                '-movflags', '+faststart',  # Optimize for web playback
                '-vf', 'scale=trunc(oh*a/2)*2:720',  # Resize to 720p maintaining aspect ratio
                '-acodec', 'aac',
                '-b:a', '128k',  # Audio bitrate
                temp_output_path
            ]
            
            subprocess.run(compress_cmd, check=True)
            
            # Create a SubmissionVideo instance with the compressed file
            video = SubmissionVideo(
                submission=submission,
                original_filename=original_filename
            )
            
            # Open and save the compressed file to the model
            with open(temp_output_path, 'rb') as compressed_file:
                video.video.save(
                    f"{Path(original_filename).stem}_compressed.mp4",
                    compressed_file,
                    save=True
                )
            
            messages.success(request, "Vídeo subido y comprimido correctamente.")
            return redirect('edit_submission', submission_id=submission.id)
            
        except subprocess.CalledProcessError as e:
            messages.error(request, f"Error al comprimir el vídeo: {str(e)}")
        finally:
            # Clean up temporary files
            if os.path.exists(temp_input_path):
                os.unlink(temp_input_path)
            if os.path.exists(temp_output_path):
                os.unlink(temp_output_path)
    else:
        messages.error(request, "Por favor, corrige los errores en el formulario.")
    
    return redirect('edit_submission', submission_id=submission.id)


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
    video.delete()
    
    messages.success(request, "Vídeo eliminado correctamente.")
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
    image.delete()
    
    messages.success(request, "Imagen eliminada correctamente.")
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
