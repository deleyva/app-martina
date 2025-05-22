from django.urls import path
from . import views
from .submission_views import (
    student_dashboard, create_submission, edit_submission, upload_video, 
    upload_image, delete_video, delete_image, teacher_view_submission
)

urlpatterns = [
    path('', views.EvaluationItemListView.as_view(), name='evaluation_item_list'),
    path('select/<int:item_id>/', views.select_students, name='select_students'),
    path('pending/', views.PendingEvaluationsView.as_view(), name='pending_evaluations'),
    path('save/<int:student_id>/', views.save_evaluation, name='save_evaluation'),
    path('toggle-classroom/<int:student_id>/', views.toggle_classroom_submission, name='toggle_classroom_submission'),
    # Nuevas URLs para la búsqueda y adición de estudiantes
    path('search-students/', views.search_students, name='search_students'),
    path('add-student-to-pending/', views.add_student_to_pending, name='add_student_to_pending'),
    
    # Dashboard del estudiante
    path('dashboard/', student_dashboard, name='student_dashboard'),
    
    # URLs para el sistema de envíos
    path('submission/create/<int:status_id>/', create_submission, name='create_submission'),
    path('submission/edit/<int:submission_id>/', edit_submission, name='edit_submission'),
    path('submission/<int:submission_id>/upload-video/', upload_video, name='upload_video'),
    path('submission/<int:submission_id>/upload-image/', upload_image, name='upload_image'),
    path('video/<int:video_id>/delete/', delete_video, name='delete_video'),
    path('image/<int:image_id>/delete/', delete_image, name='delete_image'),
    
    # Vista del profesor para submissions
    path('submission/view/<int:status_id>/', teacher_view_submission, name='teacher_view_submission'),
]
