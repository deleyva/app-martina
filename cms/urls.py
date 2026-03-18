from django.urls import path
from . import views

urlpatterns = [
    path("scores/filtered/", views.filtered_scores_view, name="filtered_scores"),
    path("scores/embed-html/", views.score_embed_html, name="score_embed_html"),
    path("ayuda/", views.help_index, name="help_index"),
    path("ayuda/<slug:slug>/", views.help_video, name="help_video"),
    path("ai-publish/", views.ai_publish_form, name="ai_publish_form"),
    path("order-scores/", views.order_scores_view, name="order_scores"),
    path("update-scores-order/", views.update_scores_order, name="update_scores_order"),
    path("resources/", views.resource_library_view, name="resource_library"),
    path("resources/save-filter/", views.save_resource_filter, name="save_resource_filter"),
    path("resources/delete-filter/<int:filter_id>/", views.delete_resource_filter, name="delete_resource_filter"),
]
