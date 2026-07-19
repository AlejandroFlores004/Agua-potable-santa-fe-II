from django.contrib import admin
from .models import Customer
from connection.models import Line


class LineInline(admin.TabularInline):
    model = Line
    extra = 1
    fields = ('description',)  # only ask for what's actually needed; code & created_by are handled automatically
    readonly_fields = ()

    def save_new_instance(self, form, formset):
        # not used directly, kept here for reference if you override further
        pass


class CustomerAdmin(admin.ModelAdmin):
    list_display = ('dui', 'firstName', 'lastName', 'email', 'number', 'created_at', 'created_by')
    search_fields = ('dui', 'firstName', 'lastName', 'email', 'number')
    list_filter = ('created_at', 'created_by')
    inlines = [LineInline]

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Line) and not instance.pk:
                instance.created_by = request.user
            instance.save()
        formset.save_m2m()

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register(Customer, CustomerAdmin)