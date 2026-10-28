from django.urls import path

from . import views

urlpatterns = [
    path('', views.reports_home, name='reports_home'),
    path('customers/', views.customers_pdf, name='report_customers'),
    path('customers/observations/', views.customer_observations_pdf, name='report_customer_observations'),
    path('customers/statement/', views.customer_statement_pdf, name='report_customer_statement'),
    path('lines/', views.lines_pdf, name='report_lines'),
    path('debtors/', views.debtors_pdf, name='report_debtors'),
    path('invoices/excel/', views.invoices_excel, name='report_invoices_excel'),
]
