from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from .models import Customer
from .validators import validate_dui, validate_phone
from connection.models import Line

INPUT_CLASSES = "input input-bordered w-full"
SELECT_CLASSES = "select select-bordered w-full"
TEXTAREA_CLASSES = "textarea textarea-bordered w-full"


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["dui", "firstName", "lastName", "email", "number"]
        widgets = {
            "dui": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "00000000-0"}),
            "firstName": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "lastName": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASSES}),
            "number": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "0000-0000"}),
        }

    @property
    def dui_warning(self):
        # Por ahora el DUI no es obligatorio ni bloquea el guardado; solo se avisa.
        dui = self.cleaned_data.get("dui")
        if not dui:
            return "El cliente no tiene DUI; regístralo en cuanto sea posible."
        try:
            validate_dui(dui)
        except ValidationError as error:
            return f"{error.messages[0]} Corrígelo en cuanto sea posible."
        return None

    def clean_number(self):
        number = self.cleaned_data.get("number")
        if number:
            validate_phone(number)
        return number


class LineForm(forms.ModelForm):
    class Meta:
        model = Line
        fields = ["location", "description", "isActive"]
        widgets = {
            "isActive": forms.CheckboxInput(attrs={"class": "toggle toggle-success toggle-sm"}),
            "location": forms.Select(attrs={"class": SELECT_CLASSES}),
            "description": forms.Textarea(
                attrs={"class": TEXTAREA_CLASSES, "rows": 2, "placeholder": "Descripción (opcional)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].required = False
        self.fields["location"].empty_label = "Selecciona una ubicación"
        self.fields["description"].required = False
        # El estado solo se edita en líneas existentes; las nuevas quedan activas por defecto.
        if not self.instance.pk:
            del self.fields["isActive"]


def get_line_formset_class(extra=0):
    return inlineformset_factory(
        Customer,
        Line,
        form=LineForm,
        extra=extra,
        can_delete=False,
    )
