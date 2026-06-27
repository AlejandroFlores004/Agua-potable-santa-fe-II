from django.contrib import admin

from billing.models import Fee, Invoice

# Register your models here.
class FeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'created_at', 'created_by')
    search_fields = ('name', 'amount', 'created_by__username')
    list_filter = ('created_at',)

admin.site.register(Fee, FeeAdmin)

class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('fee', 'start_date', 'end_date', 'due_date', 'created_at', 'created_by')
    search_fields = ('fee__name', 'created_by__username')
    list_filter = ('start_date', 'end_date', 'due_date', 'created_at')

admin.site.register(Invoice, InvoiceAdmin)