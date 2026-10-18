from django import forms
from django.db.models import Q

from billing.models import Fee
from customer.models import Customer
from .models import Line, Location

INPUT_CLASSES = "input input-bordered w-full"
SELECT_CLASSES = "select select-bordered w-full"
TEXTAREA_CLASSES = "textarea textarea-bordered w-full"


class LineForm(forms.ModelForm):
    class Meta:
        model = Line
        fields = ["customer", "location", "fee", "description"]
        widgets = {
            "fee": forms.Select(attrs={"class": SELECT_CLASSES}),
            "customer": forms.Select(attrs={"class": SELECT_CLASSES}),
            "location": forms.Select(attrs={"class": SELECT_CLASSES}),
            "description": forms.Textarea(
                attrs={"class": TEXTAREA_CLASSES, "rows": 3, "placeholder": "Descripción (opcional)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.order_by("firstName", "lastName")
        self.fields["customer"].empty_label = "Selecciona un cliente"
        # Al editar, la mecha no puede cambiar de cliente; Django ignora el valor enviado.
        if self.instance.pk:
            self.fields["customer"].disabled = True
        self.fields["location"].queryset = Location.objects.order_by("name")
        self.fields["location"].required = False
        self.fields["location"].empty_label = "Selecciona una ubicación"
        # Solo cuotas activas; se conserva la actual aunque esté desactivada.
        active_fees = Q(isActive=True)
        if self.instance.fee_id:
            active_fees |= Q(pk=self.instance.fee_id)
        self.fields["fee"].queryset = Fee.objects.filter(active_fees).order_by("name")
        self.fields["fee"].required = True
        self.fields["fee"].empty_label = "Selecciona una cuota"
        self.fields["description"].required = False
