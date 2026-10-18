from django.contrib import admin
from connection.models import Line, Location

# Register your models here.


class LineAdmin(admin.ModelAdmin):
    list_display = ('code', 'isActive', 'location', 'fee', 'description', 'customer', 'created_at', 'updated_at')
    search_fields = ('code', 'description', 'location__name', 'customer__firstName', 'customer__lastName')
    list_filter = ('isActive', 'created_at', 'updated_at', 'location', 'fee')
    readonly_fields = ('created_at', 'updated_at', 'code')

    def has_delete_permission(self, request, obj=None):
        return False


class LocationAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

admin.site.register(Line, LineAdmin)
admin.site.register(Location, LocationAdmin)

# Register your models here.
