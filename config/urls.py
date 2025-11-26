# ruff: noqa
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include
from django.urls import path
from django.views import defaults as default_views
from django.views.generic import TemplateView
from ninja import NinjaAPI, Router

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

# Crear una única instancia de NinjaAPI para toda la aplicación
api = NinjaAPI(title="Martina Bescós App API", version="1.0.0")

# Importar los routers de cada aplicación
from evaluations.api import router as evaluations_router
from api_keys.api import router as api_keys_router
from cms.api import router as cms_router

# Registrar los routers en la API principal
api.add_router("/evaluations/", evaluations_router)
api.add_router("/keys/", api_keys_router)
api.add_router("/cms/", cms_router)


@api.get("/add")
def add(request, a: int, b: int):
    return {"result": a + b}


urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path(
        "about/",
        TemplateView.as_view(template_name="pages/about.html"),
        name="about",
    ),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # NinjaApi routes
    path("api/", api.urls),
    # User management
    path("users/", include("martina_bescos_app.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
    # Your stuff: custom urls includes go here
    path("clases/", include("clases.urls")),
    path("evaluations/", include("evaluations.urls", namespace="evaluations")),
    # API Keys management UI
    path("api-keys/", include("api_keys.urls", namespace="api_keys")),
    # Song Ranking app
    path("songs/", include("songs_ranking.urls", namespace="songs_ranking")),
    # django-sql-explorer
    path("explorer/", include("explorer.urls")),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("pages/", include(wagtail_urls)),
    # My Library - Biblioteca personal de usuario
    path("my-library/", include("my_library.urls", namespace="my_library")),
    # CMS custom views (filtros de partituras)
    path("", include("cms.urls")),
    # music-pills integrado en Wagtail CMS - accesible via /cms/ y páginas públicas
    # ...
    # Media files
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
