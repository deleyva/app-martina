"""
Content Hub URL Configuration
"""

from django.urls import path

from . import views

app_name = "content_hub"

urlpatterns = [
    # Dashboard
    path("", views.ContentHubIndexView.as_view(), name="index"),

    # Quick Add
    path("add/", views.QuickAddView.as_view(), name="quick_add"),
    path("quick-add/", views.QuickAddView.as_view(), name="quick_add_alias"),  # Alias
    path("add/author/", views.QuickAddAuthorView.as_view(), name="quick_add_author"),
    path("add/song/", views.QuickAddSongView.as_view(), name="quick_add_song"),

    # Content CRUD
    path("list/", views.ContentListView.as_view(), name="list"),
    path("<int:pk>/", views.ContentDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ContentUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ContentDeleteView.as_view(), name="delete"),

    # Links
    path(
        "<int:source_pk>/link/<int:target_pk>/",
        views.create_link,
        name="create_link",
    ),

    # Categories
    path("category/<int:pk>/", views.CategoryDetailView.as_view(), name="category_detail"),

    # Knowledge Graph Visualization
    path("graph/", views.GraphView.as_view(), name="graph"),
]
