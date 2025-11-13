from django.urls import path
from . import views

app_name = "clases"

urlpatterns = [
    # =============================================================================
    # BIBLIOTECA DE GRUPO
    # =============================================================================
    path(
        "groups/<int:group_id>/library/",
        views.group_library_index,
        name="group_library_index",
    ),
    path(
        "groups/<int:group_id>/library/add/",
        views.group_library_add,
        name="group_library_add",
    ),
    path(
        "groups/<int:group_id>/library/remove/<int:pk>/",
        views.group_library_remove,
        name="group_library_remove",
    ),
    path(
        "groups/<int:group_id>/library/remove-by-content/",
        views.group_library_remove_by_content,
        name="group_library_remove_by_content",
    ),
    
    # =============================================================================
    # SESIONES DE CLASE
    # =============================================================================
    path(
        "sessions/",
        views.class_session_list,
        name="class_session_list",
    ),
    path(
        "sessions/create/",
        views.class_session_create,
        name="class_session_create",
    ),
    path(
        "sessions/<int:pk>/edit/",
        views.class_session_edit,
        name="class_session_edit",
    ),
    path(
        "sessions/<int:pk>/delete/",
        views.class_session_delete,
        name="class_session_delete",
    ),
    path(
        "sessions/<int:session_id>/add-item/",
        views.class_session_add_item,
        name="class_session_add_item",
    ),
    path(
        "sessions/<int:session_id>/remove-item/<int:item_id>/",
        views.class_session_remove_item,
        name="class_session_remove_item",
    ),
    path(
        "sessions/<int:session_id>/reorder-items/",
        views.class_session_reorder_items,
        name="class_session_reorder_items",
    ),
    
    # =============================================================================
    # BIBLIOTECA MÚLTIPLE
    # =============================================================================
    path(
        "libraries/add-multiple/",
        views.add_to_multiple_libraries,
        name="add_to_multiple_libraries",
    ),
]
