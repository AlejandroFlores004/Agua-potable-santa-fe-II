from django.urls import path
from . import views

urlpatterns = [
    path('', views.billing_home, name='billing_home'),
    path('create/', views.invoice_form, name='invoice_create'),
    path('<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('<int:pk>/summary/', views.invoice_summary, name='invoice_summary'),
    path('<int:pk>/edit/', views.invoice_form, name='invoice_edit'),
    path('<int:pk>/delete/', views.invoice_delete, name='invoice_delete'),
    path('<int:pk>/open/', views.invoice_open, name='invoice_open'),
    path('<int:pk>/close/', views.invoice_close, name='invoice_close'),
    path('<int:pk>/assign-lines/', views.invoice_assign_lines, name='invoice_assign_lines'),
    path('<int:pk>/assign-lines/confirm/', views.invoice_assign_lines_confirm, name='invoice_assign_lines_confirm'),
    path('<int:pk>/assign-line/', views.invoice_assign_line, name='invoice_assign_line'),
    path('<int:pk>/lines/', views.invoice_lines, name='invoice_lines'),
    path('<int:pk>/print/select/', views.invoice_print_select, name='invoice_print_select'),
    path('<int:pk>/print/selected/', views.invoice_print_selected, name='invoice_print_selected'),
    path('<int:pk>/print/by-status/', views.invoice_receipts_by_status_pdf, name='invoice_receipts_by_status_pdf'),
    path('<int:pk>/print/horizontal/', views.invoice_print_receipts_landscape, name='invoice_print_receipts_landscape'),
    path('invoice-lines/<int:pk>/toggle-paid/', views.invoice_line_toggle_paid, name='invoice_line_toggle_paid'),
    path('invoice-lines/<int:pk>/late-fee/', views.invoice_line_late_fee, name='invoice_line_late_fee'),
    path('invoice-lines/<int:pk>/remove/', views.invoice_line_remove, name='invoice_line_remove'),
    path('invoice-lines/<int:pk>/print/', views.invoice_line_print_receipt, name='invoice_line_print_receipt'),

    path('fees/', views.fee_home, name='fee_home'),
    path('fees/create/', views.fee_create, name='fee_create'),
    path('fees/<int:pk>/toggle/', views.fee_toggle, name='fee_toggle'),

    path('late-fees/', views.late_fee_table, name='late_fee_table'),
    path('late-fees/create/', views.late_fee_create, name='late_fee_create'),
    path('late-fees/<int:pk>/make-default/', views.late_fee_make_default, name='late_fee_make_default'),
]
