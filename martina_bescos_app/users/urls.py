from django.urls import path

from .views import user_detail_view
from .views import user_redirect_view
from .views import user_update_view
from .impersonation import (
    ImpersonateUserListView,
    ImpersonateUserView,
    ReturnFromImpersonationView,
    EndImpersonationView,
)
from .debug_profile import debug_profile_picture

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    path("<int:pk>/", view=user_detail_view, name="detail"),
    # Debug - eliminar en producción
    path("debug-profile/", view=debug_profile_picture, name="debug-profile"),
    # Rutas para la impersonación de usuarios
    path(
        "impersonate/", view=ImpersonateUserListView.as_view(), name="impersonate-list"
    ),
    path(
        "impersonate/<int:user_id>/",
        view=ImpersonateUserView.as_view(),
        name="impersonate-user",
    ),
    path(
        "impersonate/return/",
        view=ReturnFromImpersonationView.as_view(),
        name="impersonate-return",
    ),
    path(
        "impersonate/end/",
        view=EndImpersonationView.as_view(),
        name="end-impersonation",
    ),
]
