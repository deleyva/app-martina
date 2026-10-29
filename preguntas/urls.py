from django.urls import path

from . import views, views_pase

app_name = "preguntas"

urlpatterns = [
    path("", views.banco, name="banco"),
    path("nueva/", views.editar, name="nueva"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/estado/", views.cambiar_estado, name="estado"),
    # El pase en clase (tramo 76·2).
    path("pase/nuevo/", views_pase.pase_nuevo, name="pase_nuevo"),
    path("grupo/<int:group_id>/tarjetas.pdf", views_pase.tarjetas_grupo, name="tarjetas_grupo"),
    path("tarjetas.pdf", views_pase.tarjetas_genericas, name="tarjetas_genericas"),
    path("pegatinas.pdf", views_pase.pegatinas, name="pegatinas"),
    path("pase/<int:pk>/estado/", views_pase.pase_estado, name="pase_estado"),
    path("pase/<int:pk>/abrir/", views_pase.pase_abrir, name="pase_abrir"),
    path("pase/<int:pk>/leer/", views_pase.pase_leer, name="pase_leer"),
    path("pase/<int:pk>/revelar/", views_pase.pase_revelar, name="pase_revelar"),
    path("pase/<int:pk>/siguiente/", views_pase.pase_siguiente, name="pase_siguiente"),
    path("pase/<int:pk>/revisar/", views_pase.pase_revisar, name="pase_revisar"),
    path("pase/<int:pk>/anterior/", views_pase.pase_anterior, name="pase_anterior"),
    path("pase/<int:pk>/corregir/", views_pase.pase_corregir, name="pase_corregir"),
    path("pase/<int:pk>/cerrar/", views_pase.pase_cerrar, name="pase_cerrar"),
    # La teoría acumulada (tramo 76·3).
    path("grupo/<int:group_id>/teoria/", views_pase.teoria_grupo, name="teoria_grupo"),
    path("grupo/<int:group_id>/teoria/<int:alumno_id>/", views_pase.teoria_alumno, name="teoria_alumno"),
    # Prototipo de escaneo (76·0).
    path("prototipo/", views.prototipo, name="prototipo"),
    path("prototipo/detectar/", views.detectar, name="detectar"),
    path("prototipo/tarjetas.pdf", views.tarjetas_prueba, name="tarjetas_prueba"),
]
