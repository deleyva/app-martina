from django.urls import path
from . import views

urlpatterns = [
    path('scores/filtered/', views.filtered_scores_view, name='filtered_scores'),
]
