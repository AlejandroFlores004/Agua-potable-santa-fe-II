from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from shell.htmx import messages_response
from shell.pagination import paginate

from . import services
from .forms import ExpenseForm, RecurringExpenseForm
from .models import Expense, RecurringExpense


@login_required(login_url="login")
def expense_home(request):
    query = request.GET.get("q", "").strip()
    month = services.resolve_month(request.GET.get("month"))
    expenses = services.search_expenses(query, month)
    page_obj = paginate(request, expenses)
    context = {
        "expenses": page_obj.object_list,
        "page_obj": page_obj,
        "summary": services.expense_summary(expenses),
        "query": query,
        "month": month,
    }
    if request.htmx:
        return render(request, "partials/expense/_expense_table.html", context)
    return render(request, "expense_home.html", context)


@login_required(login_url="login")
def expense_form(request, pk=None):
    expense = get_object_or_404(Expense, pk=pk) if pk else Expense(date=date.today())
    is_new = expense.pk is None

    if request.method == "POST":
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            services.save_expense(form.save(commit=False), request.user)
            messages.success(
                request,
                "Gasto registrado correctamente." if is_new else "Gasto actualizado correctamente.",
            )
            return messages_response(request, "expenseSaved")
    else:
        form = ExpenseForm(instance=expense)

    return render(
        request,
        "partials/expense/_expense_form_modal.html",
        {"form": form, "expense": expense, "is_new": is_new},
    )


@login_required(login_url="login")
@require_POST
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    expense.delete()
    messages.success(request, "Gasto eliminado correctamente.")
    return messages_response(request, "expenseSaved")


@login_required(login_url="login")
def recurring_home(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "active")
    page_obj = paginate(request, services.search_recurring(query, status))
    context = {
        "plans": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "summary": services.recurring_summary(),
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
            services.save_recurring(form.save(commit=False), request.user)
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
    plan = services.toggle_recurring(get_object_or_404(RecurringExpense, pk=pk))
    messages.success(
        request,
        "Gasto recurrente activado correctamente." if plan.isActive else "Gasto recurrente desactivado correctamente.",
    )
    return messages_response(request, "recurringSaved")


@login_required(login_url="login")
@require_POST
def recurring_delete(request, pk):
    plan = get_object_or_404(RecurringExpense, pk=pk)
    try:
        services.delete_recurring(plan)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, "Gasto recurrente eliminado correctamente.")
    return messages_response(request, "recurringSaved")


@login_required(login_url="login")
def recurring_pay(request, pk):
    plan = get_object_or_404(RecurringExpense, pk=pk)
    try:
        services.ensure_payable(plan)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return messages_response(request, "recurringSaved")

    expense = services.new_payment(plan)
    if request.method == "POST":
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            services.register_payment(form.save(commit=False), request.user)
            messages.success(request, f"Pago de «{plan.name}» registrado correctamente.")
            return messages_response(request, "recurringSaved")
    else:
        form = ExpenseForm(instance=expense)

    context = {"plan": plan, "payment_number": plan.payments_count + 1, "due_date": plan.next_due_date}
    return render(request, "partials/recurring/_recurring_pay_modal.html", {"form": form, **context})
