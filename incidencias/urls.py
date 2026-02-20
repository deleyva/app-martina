from django.urls import path

from . import views

app_name = "incidencias"

urlpatterns = [
    # --- Público ---
    path("", views.LandingView.as_view(), name="landing"),
    path("buscar/", views.BuscarView.as_view(), name="buscar"),
    path("crear/", views.CrearIncidenciaView.as_view(), name="crear"),
    path("<int:pk>/", views.DetalleIncidenciaView.as_view(), name="detalle"),
    path("<int:pk>/comentar/", views.AgregarComentarioView.as_view(), name="comentar"),
    # --- API autocompletado ---
    path("api/ubicaciones/", views.ApiUbicacionesView.as_view(), name="api_ubicaciones"),
    path("api/etiquetas/", views.ApiEtiquetasView.as_view(), name="api_etiquetas"),
    # --- Panel administración ---
    path("panel/", views.PanelDashboardView.as_view(), name="panel"),
    path("panel/editar/<int:pk>/", views.EditarIncidenciaView.as_view(), name="panel_editar"),
    path("panel/asignar/<int:pk>/", views.AsignarIncidenciaView.as_view(), name="panel_asignar"),
    path("panel/estado/<int:pk>/", views.CambiarEstadoView.as_view(), name="panel_estado"),
    path("panel/api/estado/<int:pk>/", views.CambiarEstadoApiView.as_view(), name="panel_estado_api"),
    path("panel/tecnicos/", views.GestionTecnicosView.as_view(), name="panel_tecnicos"),
]
