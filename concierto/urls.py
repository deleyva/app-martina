from django.urls import path

from . import views

app_name = "concierto"

urlpatterns = [
    path("", views.ProgramaView.as_view(), name="programa"),
    path("apuntarse/<int:tarea_id>/", views.ApuntarseView.as_view(), name="apuntarse"),
    path("desapuntarse/<int:voluntario_id>/", views.DesapuntarseView.as_view(), name="desapuntarse"),
]
