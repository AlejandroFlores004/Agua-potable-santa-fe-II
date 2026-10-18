from django.contrib import admin
from expense.models import Expense, RecurringExpense


class RecurringExpenseAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'amount', 'frequency', 'start_date', 'end_date', 'total_payments', 'isActive')
    search_fields = ('name', 'description')
    list_filter = ('isActive', 'kind', 'frequency')
    readonly_fields = ('created_at', 'updated_at')


class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('concept', 'date', 'amount', 'recurring', 'created_by')
    search_fields = ('concept', 'description')
    list_filter = ('date', 'recurring')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'


admin.site.register(RecurringExpense, RecurringExpenseAdmin)
admin.site.register(Expense, ExpenseAdmin)
