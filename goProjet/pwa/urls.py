from django.urls import path
from . import views

urlpatterns = [
    path('manifest.json', views.manifest_view, name='manifest'),
    path('serviceworker.js', views.serviceworker_view, name='serviceworker'),
]