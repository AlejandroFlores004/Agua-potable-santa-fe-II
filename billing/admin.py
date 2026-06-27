from django.contrib import admin

from billing.models import Fee

# Register your models here.
class FeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'created_at', 'created_by')
    search_fields = ('name', 'amount', 'created_by__username')
    list_filter = ('created_at',)

admin.site.register(Fee, FeeAdmin)