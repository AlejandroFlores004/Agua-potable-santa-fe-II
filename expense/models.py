import calendar
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import models


def add_months(value, months):
    # Suma meses conservando el día; si no existe (31 en abril), usa el último del mes.
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class RecurringExpense(models.Model):
    """Gasto que se repite cada cierto tiempo. Cada pago se registra como un Expense."""

    class Kind(models.TextChoices):
        FIXED = "fixed", "Fijo"
        VARIABLE = "variable", "Variable"
        INSTALLMENTS = "installments", "A plazos"

    class Frequency(models.TextChoices):
        WEEKLY = "weekly", "Semanal"
        BIWEEKLY = "biweekly", "Quincenal"
        MONTHLY = "monthly", "Mensual"
        BIMONTHLY = "bimonthly", "Bimestral"
        QUARTERLY = "quarterly", "Trimestral"
        SEMIANNUAL = "semiannual", "Semestral"
        ANNUAL = "annual", "Anual"

    # Frecuencia -> (días, meses) que se avanzan entre un pago y el siguiente.
    FREQUENCY_STEP = {
        Frequency.WEEKLY: (7, 0),
        Frequency.BIWEEKLY: (14, 0),
        Frequency.MONTHLY: (0, 1),
        Frequency.BIMONTHLY: (0, 2),
        Frequency.QUARTERLY: (0, 3),
        Frequency.SEMIANNUAL: (0, 6),
        Frequency.ANNUAL: (0, 12),
    }

    name = models.CharField("Concepto", max_length=150)
    kind = models.CharField("Tipo", max_length=20, choices=Kind.choices, default=Kind.FIXED)
    amount = models.DecimalField("Monto", max_digits=10, decimal_places=2, help_text="En gastos variables es un monto estimado.")
    frequency = models.CharField("Frecuencia", max_length=20, choices=Frequency.choices, default=Frequency.MONTHLY)
    start_date = models.DateField("Primer pago")
    end_date = models.DateField("Fecha de fin", blank=True, null=True)
    total_payments = models.PositiveIntegerField("Número de pagos", blank=True, null=True)
    description = models.TextField("Descripción", blank=True, null=True)
    isActive = models.BooleanField("Activo", default=True)
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de edición", auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Creado por")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Gasto recurrente"
        verbose_name_plural = "Gastos recurrentes"
        ordering = ['name']

    def due_date_for(self, index):
        # Fecha del pago número `index` (0 = primer pago).
        days, months = self.FREQUENCY_STEP[self.frequency]
        if months:
            return add_months(self.start_date, months * index)
        return self.start_date + timedelta(days=days * index)

    @property
    def payments_count(self):
        # Usa la anotación de la vista si existe para no hacer una consulta por fila.
        if hasattr(self, "payments_total"):
            return self.payments_total
        return self.payments.count()

    @property
    def is_finished(self):
        if self.total_payments and self.payments_count >= self.total_payments:
            return True
        next_date = self.due_date_for(self.payments_count)
        return bool(self.end_date and next_date > self.end_date)

    @property
    def next_due_date(self):
        # Cada pago registrado cubre un periodo, así que el siguiente vence
        # en el periodo número `payments_count`. Si hay atraso, queda en el pasado.
        if self.is_finished:
            return None
        return self.due_date_for(self.payments_count)

    @property
    def is_overdue(self):
        next_date = self.next_due_date
        return bool(self.isActive and next_date and next_date < date.today())

    @property
    def remaining_payments(self):
        if not self.total_payments:
            return None
        return max(self.total_payments - self.payments_count, 0)


class Expense(models.Model):
    concept = models.CharField("Concepto", max_length=150)
    recurring = models.ForeignKey(RecurringExpense, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Gasto recurrente", related_name='payments')
    amount = models.DecimalField("Monto", max_digits=10, decimal_places=2)
    date = models.DateField("Fecha")
    description = models.TextField("Descripción", blank=True, null=True)
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de edición", auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Creado por")

    def __str__(self):
        return f"{self.concept} - {self.amount}"

    class Meta:
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        ordering = ['-date', '-created_at']
