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
    path("ayuda/", views.AyudaView.as_view(), name="ayuda"),
    path("servicio/<str:token>/", views.PaginaServicioView.as_view(), name="servicio_publico"),
    # --- Derivaciones (técnicos) ---
    path("<int:pk>/derivar/", views.CrearDerivacionView.as_view(), name="derivar"),
    path("derivaciones/<int:pk>/editar/", views.EditarDerivacionView.as_view(), name="derivacion_editar"),
    path("derivaciones/<int:pk>/enviada/", views.MarcarEnviadaView.as_view(), name="derivacion_enviada"),
    path("derivaciones/<int:pk>/respuesta/", views.RegistrarRespuestaView.as_view(), name="derivacion_respuesta"),
    path("derivaciones/<int:pk>/cerrar/", views.CerrarDerivacionView.as_view(), name="derivacion_cerrar"),
    # --- API autocompletado ---
    path("api/ubicaciones/", views.ApiUbicacionesView.as_view(), name="api_ubicaciones"),
    path("api/etiquetas/", views.ApiEtiquetasView.as_view(), name="api_etiquetas"),
    # --- Panel administración ---
    path("panel/", views.PanelDashboardView.as_view(), name="panel"),
    path("panel/editar/<int:pk>/", views.EditarIncidenciaView.as_view(), name="panel_editar"),
    path("panel/asignar/<int:pk>/", views.AsignarIncidenciaView.as_view(), name="panel_asignar"),
    path("panel/estado/<int:pk>/", views.CambiarEstadoView.as_view(), name="panel_estado"),
    path("panel/api/estado/<int:pk>/", views.CambiarEstadoApiView.as_view(), name="panel_estado_api"),
    path("panel/eliminar/<int:pk>/", views.EliminarIncidenciaView.as_view(), name="panel_eliminar"),
    path("panel/tecnicos/", views.GestionTecnicosView.as_view(), name="panel_tecnicos"),
    path("panel/servicios/", views.GestionServiciosView.as_view(), name="panel_servicios"),
    path("panel/servicios/nuevo/", views.EditarServicioView.as_view(), name="panel_servicio_nuevo"),
    path("panel/servicios/<int:pk>/", views.EditarServicioView.as_view(), name="panel_servicio_editar"),
]
