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
]
