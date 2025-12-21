from django.urls import path
from . import views

urlpatterns = [
    path("scores/filtered/", views.filtered_scores_view, name="filtered_scores"),
    path("scores/embed-html/", views.score_embed_html, name="score_embed_html"),
    path("ayuda/", views.help_index, name="help_index"),
    path("ayuda/<slug:slug>/", views.help_video, name="help_video"),
]
