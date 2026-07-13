from django.urls import path

from . import views

app_name = "programacion"

urlpatterns = [
    path("", views.plan_list, name="plan_list"),
    path("overview/", views.overview, name="overview"),
    path("create/", views.plan_create, name="plan_create"),
    path("<int:pk>/", views.plan_detail, name="plan_detail"),
    path("<int:pk>/delete/", views.plan_delete, name="plan_delete"),
    path("<int:pk>/items/add/", views.plan_item_add, name="plan_item_add"),
    path(
        "<int:pk>/items/<int:item_id>/remove/",
        views.plan_item_remove,
        name="plan_item_remove",
    ),
    path(
        "<int:pk>/items/<int:item_id>/status/",
        views.plan_item_status,
        name="plan_item_status",
    ),
    path(
        "<int:pk>/items/<int:item_id>/sync-chapters/",
        views.plan_item_sync_chapters,
        name="plan_item_sync_chapters",
    ),
    path(
        "<int:pk>/items/<int:item_id>/refresh-coverage/",
        views.plan_item_refresh_coverage,
        name="plan_item_refresh_coverage",
    ),
    path(
        "<int:pk>/items/<int:item_id>/create-session/",
        views.create_session_from_item,
        name="create_session_from_item",
    ),
    path("<int:pk>/reorder/", views.plan_reorder, name="plan_reorder"),
]
