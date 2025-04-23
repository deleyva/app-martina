from django.urls import path
from . import views

urlpatterns = [
    path('', views.EvaluationItemListView.as_view(), name='evaluation_item_list'),
    path('select/<int:item_id>/', views.select_students, name='select_students'),
    path('pending/', views.PendingEvaluationsView.as_view(), name='pending_evaluations'),
    path('save/<int:student_id>/', views.save_evaluation, name='save_evaluation'),
    path('toggle-classroom/<int:student_id>/', views.toggle_classroom_submission, name='toggle_classroom_submission'),
    # Nuevas URLs para la búsqueda y adición de estudiantes
    path('search-students/', views.search_students, name='search_students'),
    path('add-student-to-pending/', views.add_student_to_pending, name='add_student_to_pending'),
]
