from django.urls import path
from . import views
from .submission_views import (
    student_dashboard, create_submission, edit_submission, upload_video, 
    upload_image, delete_video, delete_image, teacher_view_submission
)

app_name = 'evaluations'

urlpatterns = [
    path('', views.EvaluationItemListView.as_view(), name='evaluation_item_list'),
    path('select/<int:item_id>/', views.select_students, name='select_students'),
    path('pending/', views.PendingEvaluationsView.as_view(), name='pending_evaluations'),
    path('pending/table/', views.PendingEvaluationsTableView.as_view(), name='pending_evaluations_table'),
    path('student/<int:student_id>/evaluation/<int:evaluation_item_id>/', views.StudentEvaluationDetailView.as_view(), name='student_evaluation_detail'),
    path('save/<int:student_id>/', views.save_evaluation, name='save_evaluation'),
    path('toggle-classroom/<int:student_id>/', views.toggle_classroom_submission, name='toggle_classroom_submission'),
    # Nuevas URLs para la búsqueda y adición de estudiantes
    path('search-students/', views.search_students, name='search_students'),
    path('add-student-to-pending/', views.add_student_to_pending, name='add_student_to_pending'),
    # URL para procesar retroalimentación con IA
    path('process-feedback-with-ai/', views.process_feedback_with_ai, name='process_feedback_with_ai'),
    
    # Dashboard del estudiante
    path('dashboard/', student_dashboard, name='student_dashboard'),
    path('student-dashboard/<int:student_id>/', views.teacher_view_student_dashboard, name='teacher_view_student_dashboard'),
    
    # URLs para el sistema de envíos
    path('submission/create/<int:status_id>/', create_submission, name='create_submission'),
    path('submission/edit/<int:submission_id>/', edit_submission, name='edit_submission'),
    path('submission/<int:submission_id>/upload-video/', upload_video, name='upload_video'),
    path('submission/<int:submission_id>/upload-image/', upload_image, name='upload_image'),
    path('video/<int:video_id>/delete/', delete_video, name='delete_video'),
    path('image/<int:image_id>/delete/', delete_image, name='delete_image'),
    
    # Vista del profesor para submissions
    path('submission/view/<int:status_id>/', teacher_view_submission, name='teacher_view_submission'),
    
    # URLs para biblioteca de grupo
    path('group-library/<int:group_id>/', views.group_library_index, name='group_library_index'),
    path('group-library/<int:group_id>/add/', views.group_library_add, name='group_library_add'),
    path('group-library/<int:group_id>/remove/<int:pk>/', views.group_library_remove, name='group_library_remove'),
    path('group-library/<int:group_id>/remove-by-content/', views.group_library_remove_by_content, name='group_library_remove_by_content'),
    
    # URLs para sesiones de clase
    path('class-sessions/', views.class_session_list, name='class_session_list'),
    path('class-sessions/create/', views.class_session_create, name='class_session_create'),
    path('class-sessions/<int:pk>/edit/', views.class_session_edit, name='class_session_edit'),
    path('class-sessions/<int:pk>/delete/', views.class_session_delete, name='class_session_delete'),
    path('class-sessions/<int:session_id>/add-item/', views.class_session_add_item, name='class_session_add_item'),
    path('class-sessions/<int:session_id>/remove-item/<int:item_id>/', views.class_session_remove_item, name='class_session_remove_item'),
    path('class-sessions/<int:session_id>/reorder/', views.class_session_reorder_items, name='class_session_reorder_items'),
    
    # URL para añadir a múltiples bibliotecas (personal + grupos)
    path('add-to-multiple-libraries/', views.add_to_multiple_libraries, name='add_to_multiple_libraries'),
]
