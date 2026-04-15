from django.urls import path
from . import views

app_name = "my_library"

urlpatterns = [
    path("", views.my_library_index, name="index"),
    path("add/", views.add_to_library, name="add"),
    path("remove/<int:pk>/", views.remove_from_library, name="remove"),
    path("remove-by-content/", views.remove_by_content, name="remove_by_content"),
    path("view/<int:pk>/", views.view_library_item, name="view_item"),
    path(
        "view-content/<int:content_type_id>/<int:object_id>/",
        views.view_content_object,
        name="view_content_object",
    ),
    path("proficiency/<int:pk>/", views.update_proficiency, name="update_proficiency"),
    path("update-title/<int:pk>/", views.update_item_title, name="update_title"),
    path("update-tags/<int:pk>/", views.update_item_tags, name="update_tags"),
    path("suggest-tags/", views.suggest_tags, name="suggest_tags"),
    path("study/", views.study_session_view, name="study_session"),
    path("study-item/<int:pk>/", views.study_item_content, name="study_item_content"),
    path("mark-viewed/<int:pk>/", views.mark_viewed, name="mark_viewed"),
]
