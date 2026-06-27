from django.contrib import admin
from connection.models import Line

# Register your models here.


class LineAdmin(admin.ModelAdmin):
    list_display = ('code', 'description', 'customer', 'created_at', 'updated_at')
    search_fields = ('code', 'description', 'customer__firstName', 'customer__lastName')
    list_filter = ('created_at', 'updated_at', 'customer')
    readonly_fields = ('created_at', 'updated_at', 'code')

admin.site.register(Line, LineAdmin)