from django.urls import path

from repertorio import views

app_name = "repertorio"

urlpatterns = [
    path("", views.catalogo, name="catalogo"),
]
