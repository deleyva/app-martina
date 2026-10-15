from django.urls import path

from . import views

app_name = "preguntas"

urlpatterns = [
    path("prototipo/", views.prototipo, name="prototipo"),
    path("prototipo/detectar/", views.detectar, name="detectar"),
    path("prototipo/tarjetas.pdf", views.tarjetas_prueba, name="tarjetas_prueba"),
]
