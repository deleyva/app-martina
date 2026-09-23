from django.urls import path

from . import views

app_name = "calificaciones"

urlpatterns = [
    path("", views.index, name="index"),
    # El cuadro de un grupo (?t=1|2|3)
    path("grupo/<int:group_id>/", views.cuadro, name="cuadro"),
    path("grupo/<int:group_id>/plan/adoptar/", views.plan_adoptar, name="plan_adoptar"),
    path("grupo/<int:group_id>/nota/", views.nota_guardar, name="nota_guardar"),
    path("grupo/<int:group_id>/nota-manual/", views.nota_manual_guardar, name="nota_manual_guardar"),
    path(
        "grupo/<int:group_id>/instrumento/<int:instrumento_id>/alumno/<int:alumno_id>/",
        views.panel,
        name="panel",
    ),
    path("grupo/<int:group_id>/clase/", views.clase, name="clase"),
    path("grupo/<int:group_id>/evidencia/", views.evidencia_subir, name="evidencia_subir"),
    path("grupo/<int:group_id>/historial/", views.historial, name="historial"),
    path("grupo/<int:group_id>/exportar/", views.exportar, name="exportar"),
    # El plan: instrumentos, reparto y pruebas
    path("plan/<int:plan_id>/", views.plan, name="plan"),
    path("plan/<int:plan_id>/reparto/", views.reparto_guardar, name="reparto_guardar"),
    path("plan/<int:plan_id>/instrumento/", views.instrumento_crear, name="instrumento_crear"),
    path("instrumento/<int:pk>/", views.instrumento_editar, name="instrumento_editar"),
    path("instrumento/<int:instrumento_id>/prueba/", views.prueba_crear, name="prueba_crear"),
    path("prueba/<int:pk>/", views.prueba_editar, name="prueba_editar"),
    # Evidencias e historial
    path("evidencia/<int:pk>/", views.evidencia_ver, name="evidencia_ver"),
    path("evidencia/<int:pk>/borrar/", views.evidencia_borrar, name="evidencia_borrar"),
    path("cambio/<int:pk>/revertir/", views.cambio_revertir, name="cambio_revertir"),
]
