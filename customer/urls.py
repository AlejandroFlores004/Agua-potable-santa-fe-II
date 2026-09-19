from django.urls import path

from . import views as view

urlpatterns = [
    path('', view.customer_home, name='customer_home'),
    path('create/', view.customer_form, name='customer_create'),
    path('<int:pk>/edit/', view.customer_form, name='customer_edit'),
    path('<int:pk>/delete/', view.customer_delete, name='customer_delete'),
]
