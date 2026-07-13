from django.contrib import admin
from .models import Customer

# Register your models here.
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('dui', 'firstName', 'lastName', 'email', 'number', 'created_at', 'created_by')
    search_fields = ('dui', 'firstName', 'lastName', 'email', 'number')
    list_filter = ('created_at', 'created_by')

admin.site.register(Customer, CustomerAdmin)
