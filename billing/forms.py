from django import forms

from .models import Fee, Invoice

INPUT_CLASSES = "input input-bordered w-full"
SELECT_CLASSES = "select select-bordered w-full"


class FeeForm(forms.ModelForm):
    class Meta:
        model = Fee
        fields = ["name", "amount"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "amount": forms.NumberInput(attrs={"class": INPUT_CLASSES, "step": "0.01", "min": "0"}),
        }


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["fee", "start_date", "end_date", "due_date"]
        widgets = {
            "fee": forms.Select(attrs={"class": SELECT_CLASSES}),
            "start_date": forms.DateInput(attrs={"class": INPUT_CLASSES, "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": INPUT_CLASSES, "type": "date"}),
            "due_date": forms.DateInput(attrs={"class": INPUT_CLASSES, "type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        due_date = cleaned_data.get("due_date")

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "La fecha de fin no puede ser anterior a la fecha de inicio.")
        if end_date and due_date and due_date < end_date:
            self.add_error("due_date", "La fecha de vencimiento no puede ser anterior a la fecha de fin.")

        return cleaned_data
