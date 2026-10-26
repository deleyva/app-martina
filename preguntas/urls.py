from django.urls import path

from . import views

app_name = "preguntas"

urlpatterns = [
    path("", views.banco, name="banco"),
    path("nueva/", views.editar, name="nueva"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/estado/", views.cambiar_estado, name="estado"),
    path("prototipo/", views.prototipo, name="prototipo"),
    path("prototipo/detectar/", views.detectar, name="detectar"),
    path("prototipo/tarjetas.pdf", views.tarjetas_prueba, name="tarjetas_prueba"),
]
