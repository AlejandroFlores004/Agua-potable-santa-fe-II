from django.urls import path
from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("terminos/", views.terms_view, name="terms"),
]
