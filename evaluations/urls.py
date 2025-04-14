from django.urls import path
from . import views

urlpatterns = [
    path('', views.EvaluationItemListView.as_view(), name='evaluation_item_list'),
    path('select/<int:item_id>/', views.select_students, name='select_students'),
    path('pending/', views.PendingEvaluationsView.as_view(), name='pending_evaluations'),
    path('save/<int:student_id>/', views.save_evaluation, name='save_evaluation'),
    path('toggle-classroom/<int:student_id>/', views.toggle_classroom_submission, name='toggle_classroom_submission'),
]
