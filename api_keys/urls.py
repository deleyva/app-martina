from django.urls import path
from . import views

app_name = "api_keys"

urlpatterns = [
    path("", views.api_key_list, name="list"),
    path("create/", views.api_key_create, name="create"),
    path("<int:pk>/delete/", views.api_key_delete, name="delete"),
    path("<int:pk>/toggle/", views.api_key_toggle, name="toggle"),
]
