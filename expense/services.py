from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum

from .models import Expense, RecurringExpense, add_months

# Veces que ocurre cada frecuencia en un mes, para estimar el gasto mensual.
MONTHLY_FACTOR = {
    RecurringExpense.Frequency.WEEKLY: Decimal(52) / 12,
    RecurringExpense.Frequency.BIWEEKLY: Decimal(26) / 12,
    RecurringExpense.Frequency.MONTHLY: Decimal(1),
    RecurringExpense.Frequency.BIMONTHLY: Decimal(1) / 2,
    RecurringExpense.Frequency.QUARTERLY: Decimal(1) / 3,
    RecurringExpense.Frequency.SEMIANNUAL: Decimal(1) / 6,
    RecurringExpense.Frequency.ANNUAL: Decimal(1) / 12,
}


# ===== Gastos =====

def resolve_month(value):
    # Sin valor (None) se muestra el mes actual; con "" o un mes inválido, todo el historial.
    if value is None:
        return date.today().strftime("%Y-%m")
    month = value.strip()
    try:
        date.fromisoformat(f"{month}-01")
    except ValueError:
        return ""
    return month


def search_expenses(query="", month=""):
    expenses = Expense.objects.select_related("recurring", "created_by")
    if query:
        expenses = expenses.filter(Q(concept__icontains=query) | Q(description__icontains=query))
    if month:
        first_day = date.fromisoformat(f"{month}-01")
        expenses = expenses.filter(date__gte=first_day, date__lt=add_months(first_day, 1))
    return expenses.order_by("-date", "-created_at")


def expense_summary(expenses):
    totals = expenses.aggregate(
        total=Sum("amount"),
        count=Count("id"),
        recurring_total=Sum("amount", filter=Q(recurring__isnull=False)),
        recurring_count=Count("id", filter=Q(recurring__isnull=False)),
    )
    total = totals["total"] or Decimal(0)
    recurring_total = totals["recurring_total"] or Decimal(0)
    return {
        "total": total,
        "count": totals["count"],
        "recurring_total": recurring_total,
        "recurring_count": totals["recurring_count"],
        "other_total": total - recurring_total,
        "other_count": totals["count"] - totals["recurring_count"],
    }


def save_expense(expense, user):
    if expense.pk is None:
        expense.created_by = user
    expense.save()
    return expense


# ===== Gastos recurrentes =====

def search_recurring(query="", status="active"):
    recurring = (
        RecurringExpense.objects.select_related("created_by")
        .annotate(payments_total=Count("payments"), paid_amount=Sum("payments__amount"))
        .order_by("name")
    )
    if query:
        recurring = recurring.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if status == "active":
        recurring = recurring.filter(isActive=True)
    elif status == "inactive":
        recurring = recurring.filter(isActive=False)
    return recurring


def recurring_summary():
    plans = [
        plan
        for plan in RecurringExpense.objects.filter(isActive=True).annotate(payments_total=Count("payments"))
        if not plan.is_finished
    ]
    month_start = date.today().replace(day=1)
    month_end = add_months(month_start, 1)
    monthly_estimate = sum((plan.amount * MONTHLY_FACTOR[plan.frequency] for plan in plans), Decimal(0))
    return {
        "active_count": len(plans),
        "monthly_estimate": monthly_estimate,
        "annual_estimate": monthly_estimate * 12,
        "overdue": [plan for plan in plans if plan.is_overdue],
        "due_this_month": [plan for plan in plans if month_start <= plan.next_due_date < month_end],
    }


def save_recurring(plan, user):
    if plan.pk is None:
        plan.created_by = user
    plan.save()
    return plan


def toggle_recurring(plan):
    plan.isActive = not plan.isActive
    plan.save(update_fields=["isActive", "updated_at"])
    return plan


def delete_recurring(plan):
    # Los pagos registrados son historial; con pagos solo se puede desactivar.
    if plan.payments.exists():
        raise ValidationError("No se puede eliminar un gasto recurrente con pagos. Desactívalo en su lugar.")
    plan.delete()


def ensure_payable(plan):
    if plan.is_finished or not plan.isActive:
        raise ValidationError("Este gasto recurrente ya no admite pagos.")


def new_payment(plan):
    # Pago sin guardar, prellenado con los datos del gasto recurrente.
    return Expense(recurring=plan, concept=plan.name, amount=plan.amount, date=date.today())


def register_payment(expense, user):
    expense.created_by = user
    expense.save()
    return expense
