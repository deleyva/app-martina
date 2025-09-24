# cards/urls.py

from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "music_cards"

urlpatterns = [
    path(
        "",
        TemplateView.as_view(template_name="music_cards/partials/counter.html"),
        name="counter",
    ),
    path("start-study-session", views.start_study_session, name="start_study_session"),
    path(
        "finish-study-session/<int:study_session_id>/",
        views.finish_study_session,
        name="finish_study_session",
    ),
    path("study/<int:study_session_id>/", views.study_session, name="study_session"),
    path("study/item/", views.study_item, name="study_item"),
    path(
        "music-items/",
        views.FilterableMusicItemListView.as_view(),
        name="music_items_list",
    ),
    path("categories/", views.CategoryListView.as_view(), name="categories_list"),
    path("texts/<int:pk>/duplicate/", views.duplicate_text, name="duplicate_text"),
    path(
        "music-item/<int:pk>/",
        views.MusicItemDetailView.as_view(),
        name="music_item_detail",
    ),
    path("create/", views.create_text, name="create_text"),
    path("categories/<int:pk>", views.category_detail, name="category_detail"),
]

htmx_patterns = [
    path("update-order/", views.update_order, name="update_order"),
    path("delete-text/<int:pk>/", views.delete_text, name="delete_text"),
    path("text-detail/<int:pk>/", views.text_detail, name="text_detail"),
]

urlpatterns += htmx_patterns
