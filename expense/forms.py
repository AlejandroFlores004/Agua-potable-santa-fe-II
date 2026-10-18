from django import forms

from .models import Expense, RecurringExpense

INPUT_CLASSES = "input input-bordered w-full"
SELECT_CLASSES = "select select-bordered w-full"
TEXTAREA_CLASSES = "textarea textarea-bordered w-full"


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["concept", "amount", "date", "description"]
        widgets = {
            "concept": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "Ej. Compra de cloro"}),
            "amount": forms.NumberInput(attrs={"class": INPUT_CLASSES, "step": "0.01", "min": "0"}),
            "date": forms.DateInput(attrs={"class": INPUT_CLASSES, "type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(
                attrs={"class": TEXTAREA_CLASSES, "rows": 3, "placeholder": "Descripción (opcional)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount is not None and amount <= 0:
            raise forms.ValidationError("El monto debe ser mayor a cero.")
        return amount


class RecurringExpenseForm(forms.ModelForm):
    class Meta:
        model = RecurringExpense
        fields = ["name", "kind", "amount", "frequency", "start_date", "end_date", "total_payments", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "Ej. Luz de la bomba"}),
            "kind": forms.Select(attrs={"class": SELECT_CLASSES}),
            "amount": forms.NumberInput(attrs={"class": INPUT_CLASSES, "step": "0.01", "min": "0"}),
            "frequency": forms.Select(attrs={"class": SELECT_CLASSES}),
            "start_date": forms.DateInput(attrs={"class": INPUT_CLASSES, "type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"class": INPUT_CLASSES, "type": "date"}, format="%Y-%m-%d"),
            "total_payments": forms.NumberInput(attrs={"class": INPUT_CLASSES, "min": "1", "placeholder": "Ej. 12"}),
            "description": forms.Textarea(
                attrs={"class": TEXTAREA_CLASSES, "rows": 3, "placeholder": "Descripción (opcional)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["end_date"].required = False
        self.fields["total_payments"].required = False
        self.fields["description"].required = False

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get("amount")
        kind = cleaned_data.get("kind")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        total_payments = cleaned_data.get("total_payments")

        if amount is not None and amount <= 0:
            self.add_error("amount", "El monto debe ser mayor a cero.")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "La fecha de fin no puede ser anterior al primer pago.")
        if kind == RecurringExpense.Kind.INSTALLMENTS and not total_payments:
            self.add_error("total_payments", "Indica en cuántos pagos se liquida el gasto a plazos.")
        if total_payments is not None and total_payments < 1:
            self.add_error("total_payments", "Debe haber al menos un pago.")
        if self.instance.pk and total_payments and total_payments < self.instance.payments.count():
            self.add_error("total_payments", "Ya hay más pagos registrados que ese número.")
        return cleaned_data
