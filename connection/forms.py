from django import forms

from customer.models import Customer
from .models import Line, Location

INPUT_CLASSES = "input input-bordered w-full"
SELECT_CLASSES = "select select-bordered w-full"
TEXTAREA_CLASSES = "textarea textarea-bordered w-full"


class LineForm(forms.ModelForm):
    class Meta:
        model = Line
        fields = ["customer", "location", "description"]
        widgets = {
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
        self.fields["location"].queryset = Location.objects.order_by("name")
        self.fields["location"].required = False
        self.fields["location"].empty_label = "Selecciona una ubicación"
        self.fields["description"].required = False
