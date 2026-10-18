from django.contrib import admin

from billing.models import Account, Fee, Invoice, InvoiceLine, LateFee

# Register your models here.
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'number', 'created_at', 'created_by')
    search_fields = ('name', 'number', 'created_by__username')
    list_filter = ('created_at',)

admin.site.register(Account, AccountAdmin)

class FeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'isActive', 'created_at', 'created_by')
    search_fields = ('name', 'amount', 'created_by__username')
    list_filter = ('isActive', 'created_at')

    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(Fee, FeeAdmin)

class LateFeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'isDefault', 'created_at', 'created_by')
    search_fields = ('name', 'amount', 'created_by__username')
    list_filter = ('isDefault', 'created_at')

admin.site.register(LateFee, LateFeeAdmin)

class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'account', 'start_date', 'end_date', 'due_date', 'status', 'created_at', 'created_by')
    search_fields = ('account__name', 'account__number', 'created_by__username')
    list_filter = ('status', 'start_date', 'end_date', 'due_date', 'created_at')

admin.site.register(Invoice, InvoiceAdmin)

class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ('code', 'invoice', 'line', 'fee', 'amount', 'previous_balance', 'late_fee_amount', 'carried_to', 'isPaid', 'created_at', 'created_by')
    search_fields = ('code', 'fee__name', 'line__code', 'line__customer__firstName', 'line__customer__lastName', 'created_by__username')
    list_filter = ('isPaid', 'created_at')
    readonly_fields = ('code', 'created_at')

admin.site.register(InvoiceLine, InvoiceLineAdmin)
    
# Register your models here.
