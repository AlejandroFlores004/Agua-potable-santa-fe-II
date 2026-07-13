from django.urls import path, include
from . import views as view

urlpatterns = [
    path('', view.customer_home, name='customer_home'),
]