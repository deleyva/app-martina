from django.urls import path

from . import views

app_name = "libreta"

urlpatterns = [
    path("", views.index, name="index"),
    path("crear/", views.crear, name="crear"),
    path("<int:pk>/", views.editar, name="editar"),
    path("<int:pk>/ajustes/", views.ajustes, name="ajustes"),
    path("<int:pk>/borrar/", views.borrar, name="borrar"),
    path("<int:pk>/anadir/", views.anadir, name="anadir"),
    path("<int:pk>/buscar/", views.buscar, name="buscar"),
    path("<int:pk>/libreta.pdf", views.pdf, name="pdf"),
    path("<int:pk>/pedido.pdf", views.pedido, name="pedido"),
    path("elemento/<int:pk>/", views.elemento_guardar, name="elemento_guardar"),
    path("elemento/<int:pk>/mover/", views.elemento_mover, name="elemento_mover"),
    path("elemento/<int:pk>/borrar/", views.elemento_borrar, name="elemento_borrar"),
]
