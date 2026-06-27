from django.contrib import admin

from billing.models import Fee, Invoice, InvoiceLine

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

class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ('code', 'invoice', 'line', 'isPaid', 'created_at', 'created_by')
    search_fields = ('code', 'invoice__fee__name', 'line__code', 'line__customer__firstName', 'line__customer__lastName', 'created_by__username')
    list_filter = ('isPaid', 'created_at')
    readonly_fields = ('code', 'created_at')

admin.site.register(InvoiceLine, InvoiceLineAdmin)
    