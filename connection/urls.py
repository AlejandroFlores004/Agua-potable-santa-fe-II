from django.urls import path

from . import views as view

urlpatterns = [
    path('', view.line_home, name='mechas'),
    path('create/', view.line_form, name='line_create'),
    path('<int:pk>/edit/', view.line_form, name='line_edit'),
    path('<int:pk>/delete/', view.line_delete, name='line_delete'),
]
