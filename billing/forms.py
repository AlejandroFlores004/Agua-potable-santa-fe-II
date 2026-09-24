from django import forms

from connection.models import Line

from .models import Account, Fee, Invoice, InvoiceLine

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
        fields = ["fee", "account", "start_date", "end_date", "due_date"]
        widgets = {
            "fee": forms.Select(attrs={"class": SELECT_CLASSES}),
            "account": forms.Select(attrs={"class": SELECT_CLASSES}),
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


class InvoiceLineAssignForm(forms.Form):
    line = forms.ModelChoiceField(
        label="Línea",
        queryset=Line.objects.none(),
        widget=forms.Select(attrs={"class": SELECT_CLASSES}),
        empty_label="Selecciona una línea",
    )

    def __init__(self, *args, invoice, **kwargs):
        super().__init__(*args, **kwargs)
        assigned_line_ids = InvoiceLine.objects.filter(invoice=invoice).values_list("line_id", flat=True)
        self.fields["line"].queryset = (
            Line.objects.exclude(id__in=assigned_line_ids)
            .select_related("customer", "location")
            .order_by("-isActive", "code")
        )
        self.fields["line"].label_from_instance = self._line_label

    @staticmethod
    def _line_label(line):
        label = f"{line.code} — {line.customer.firstName} {line.customer.lastName}"
        if line.location:
            label += f" ({line.location})"
        if not line.isActive:
            label += " [inactiva]"
        return label
