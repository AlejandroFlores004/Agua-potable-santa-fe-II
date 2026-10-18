from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from shell.htmx import messages_response
from shell.pagination import paginate

from .forms import ExpenseForm, RecurringExpenseForm
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


def _parse_month(request):
    # Sin parámetro se muestra el mes actual; con "month=" vacío, todo el historial.
    if "month" not in request.GET:
        return date.today().strftime("%Y-%m")
    month = request.GET.get("month", "").strip()
    try:
        date.fromisoformat(f"{month}-01")
    except ValueError:
        return ""
    return month


def _get_expenses(request):
    expenses = Expense.objects.select_related("recurring", "created_by")
    query = request.GET.get("q", "").strip()
    month = _parse_month(request)
    if query:
        expenses = expenses.filter(Q(concept__icontains=query) | Q(description__icontains=query))
    if month:
        first_day = date.fromisoformat(f"{month}-01")
        expenses = expenses.filter(date__gte=first_day, date__lt=add_months(first_day, 1))
    return expenses.order_by("-date", "-created_at"), query, month


def _expense_summary(expenses):
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


@login_required(login_url="login")
def expense_home(request):
    expenses, query, month = _get_expenses(request)
    page_obj = paginate(request, expenses)
    context = {
        "expenses": page_obj.object_list,
        "page_obj": page_obj,
        "summary": _expense_summary(expenses),
        "query": query,
        "month": month,
    }
    if request.htmx:
        return render(request, "partials/expense/_expense_table.html", context)
    return render(request, "expense_home.html", context)


def _render_expense_form(request, form, expense, is_new):
    return render(
        request,
        "partials/expense/_expense_form_modal.html",
        {"form": form, "expense": expense, "is_new": is_new},
    )


@login_required(login_url="login")
def expense_form(request, pk=None):
    expense = get_object_or_404(Expense, pk=pk) if pk else Expense(date=date.today())
    is_new = expense.pk is None

    if request.method == "POST":
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            expense = form.save(commit=False)
            if is_new:
                expense.created_by = request.user
            expense.save()
            messages.success(
                request,
                "Gasto registrado correctamente." if is_new else "Gasto actualizado correctamente.",
            )
            return messages_response(request, "expenseSaved")
        return _render_expense_form(request, form, expense, is_new)

    return _render_expense_form(request, ExpenseForm(instance=expense), expense, is_new)


@login_required(login_url="login")
@require_POST
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    expense.delete()
    messages.success(request, "Gasto eliminado correctamente.")
    return messages_response(request, "expenseSaved")


def _get_recurring(request):
    recurring = (
        RecurringExpense.objects.select_related("created_by")
        .annotate(payments_total=Count("payments"), paid_amount=Sum("payments__amount"))
        .order_by("name")
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "active")
    if query:
        recurring = recurring.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if status == "active":
        recurring = recurring.filter(isActive=True)
    elif status == "inactive":
        recurring = recurring.filter(isActive=False)
    return recurring, query, status


def _recurring_summary():
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


@login_required(login_url="login")
def recurring_home(request):
    recurring, query, status = _get_recurring(request)
    page_obj = paginate(request, recurring)
    context = {
        "plans": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "summary": _recurring_summary(),
    }
    if request.htmx:
        return render(request, "partials/recurring/_recurring_table.html", context)
    return render(request, "recurring_home.html", context)


@login_required(login_url="login")
def recurring_form(request, pk=None):
    plan = get_object_or_404(RecurringExpense, pk=pk) if pk else RecurringExpense(start_date=date.today())
    is_new = plan.pk is None

    if request.method == "POST":
        form = RecurringExpenseForm(request.POST, instance=plan)
        if form.is_valid():
            plan = form.save(commit=False)
            if is_new:
                plan.created_by = request.user
            plan.save()
            messages.success(
                request,
                "Gasto recurrente creado correctamente." if is_new else "Gasto recurrente actualizado correctamente.",
            )
            return messages_response(request, "recurringSaved")
    else:
        form = RecurringExpenseForm(instance=plan)

    return render(
        request,
        "partials/recurring/_recurring_form_modal.html",
        {"form": form, "plan": plan, "is_new": is_new},
    )


@login_required(login_url="login")
@require_POST
def recurring_toggle(request, pk):
    plan = get_object_or_404(RecurringExpense, pk=pk)
    plan.isActive = not plan.isActive
    plan.save(update_fields=["isActive", "updated_at"])
    messages.success(
        request,
        "Gasto recurrente activado correctamente." if plan.isActive else "Gasto recurrente desactivado correctamente.",
    )
    return messages_response(request, "recurringSaved")


@login_required(login_url="login")
@require_POST
def recurring_delete(request, pk):
    plan = get_object_or_404(RecurringExpense, pk=pk)
    # Los pagos registrados son historial; con pagos solo se puede desactivar.
    if plan.payments.exists():
        messages.error(request, "No se puede eliminar un gasto recurrente con pagos. Desactívalo en su lugar.")
    else:
        plan.delete()
        messages.success(request, "Gasto recurrente eliminado correctamente.")
    return messages_response(request, "recurringSaved")


@login_required(login_url="login")
def recurring_pay(request, pk):
    plan = get_object_or_404(RecurringExpense, pk=pk)
    expense = Expense(
        recurring=plan,
        concept=plan.name,
        amount=plan.amount,
        date=date.today(),
    )
    context = {"plan": plan, "payment_number": plan.payments_count + 1, "due_date": plan.next_due_date}

    if plan.is_finished or not plan.isActive:
        messages.error(request, "Este gasto recurrente ya no admite pagos.")
        return messages_response(request, "recurringSaved")

    if request.method == "POST":
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            expense.save()
            messages.success(request, f"Pago de «{plan.name}» registrado correctamente.")
            return messages_response(request, "recurringSaved")
    else:
        form = ExpenseForm(instance=expense)

    return render(request, "partials/recurring/_recurring_pay_modal.html", {"form": form, **context})
