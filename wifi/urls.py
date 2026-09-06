from django.urls import path

from . import views

app_name = "wifi"

urlpatterns = [
    path("", views.SolicitarView.as_view(), name="solicitar"),
    path("gestion/", views.GestionView.as_view(), name="gestion"),
    path("gestion/anadidas/", views.MarcarAnadidasView.as_view(), name="marcar_anadidas"),
    path("gestion/baja/<int:pk>/", views.MarcarParaBajaView.as_view(), name="marcar_para_baja"),
    path("gestion/bajas-hechas/", views.MarcarBajasHechasView.as_view(), name="marcar_bajas_hechas"),
]
