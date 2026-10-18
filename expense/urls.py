from django.urls import path

from . import views as view

urlpatterns = [
    path('', view.expense_home, name='expense_home'),
    path('create/', view.expense_form, name='expense_create'),
    path('<int:pk>/edit/', view.expense_form, name='expense_edit'),
    path('<int:pk>/delete/', view.expense_delete, name='expense_delete'),
    path('recurring/', view.recurring_home, name='recurring_home'),
    path('recurring/create/', view.recurring_form, name='recurring_create'),
    path('recurring/<int:pk>/edit/', view.recurring_form, name='recurring_edit'),
    path('recurring/<int:pk>/toggle/', view.recurring_toggle, name='recurring_toggle'),
    path('recurring/<int:pk>/delete/', view.recurring_delete, name='recurring_delete'),
    path('recurring/<int:pk>/pay/', view.recurring_pay, name='recurring_pay'),
]
