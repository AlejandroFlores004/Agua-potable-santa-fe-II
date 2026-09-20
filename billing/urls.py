from django.urls import path
from . import views

urlpatterns = [
    path('', views.billing_home, name='billing_home'),
    path('create/', views.invoice_form, name='invoice_create'),
    path('<int:pk>/edit/', views.invoice_form, name='invoice_edit'),
    path('<int:pk>/delete/', views.invoice_delete, name='invoice_delete'),
    path('<int:pk>/assign-lines/', views.invoice_assign_lines, name='invoice_assign_lines'),
    path('<int:pk>/assign-lines/confirm/', views.invoice_assign_lines_confirm, name='invoice_assign_lines_confirm'),
    path('<int:pk>/lines/', views.invoice_lines, name='invoice_lines'),
    path('<int:pk>/print/', views.invoice_print_receipts, name='invoice_print_receipts'),
    path('<int:pk>/print/horizontal/', views.invoice_print_receipts_landscape, name='invoice_print_receipts_landscape'),

    path('fees/', views.fee_home, name='fee_home'),
    path('fees/create/', views.fee_create, name='fee_create'),
    path('fees/<int:pk>/delete/', views.fee_delete, name='fee_delete'),
]
