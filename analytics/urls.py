from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('track/', views.track_activity, name='track_activity'),
    path('dashboard/', views.analytics_dashboard, name='dashboard'),
]
