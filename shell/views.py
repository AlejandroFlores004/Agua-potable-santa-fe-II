from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Count, Q, Sum
from django.utils import timezone

from billing.models import Invoice, InvoiceLine
from connection.models import Line
from customer.models import Customer


def _percent(part, total):
    return round(part * 100 / total) if total else 0


def _dashboard_context():
    today = timezone.localdate()

    line_counts = Line.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(isActive=True)),
        active_without_fee=Count("id", filter=Q(isActive=True, fee__isnull=True)),
    )
    customers_total = Customer.objects.count()
    customers_without_lines = Customer.objects.filter(lines__isnull=True).count()

    # Receipts still unpaid across every invoice.
    pending = InvoiceLine.objects.filter(isPaid=False).aggregate(
        count=Count("id"), amount=Sum("amount")
    )
    # Una factura en borrador todavía no se entregó, así que sus recibos no pueden estar vencidos.
    overdue = InvoiceLine.objects.filter(isPaid=False, invoice__due_date__lt=today).exclude(
        invoice__status=Invoice.Status.DRAFT
    ).aggregate(
        count=Count("id"), amount=Sum("amount")
    )

    recent_invoices = list(
        Invoice.objects.select_related("account")
        .annotate(
            lines_count=Count("invoiceline"),
            paid_count=Count("invoiceline", filter=Q(invoiceline__isPaid=True)),
            expected_amount=Sum("invoiceline__amount"),
            collected_amount=Sum("invoiceline__amount", filter=Q(invoiceline__isPaid=True)),
        )
        .order_by("-start_date", "-created_at")[:6]
    )
    for invoice in recent_invoices:
        invoice.expected_amount = invoice.expected_amount or 0
        invoice.collected_amount = invoice.collected_amount or 0
        invoice.pending_count = invoice.lines_count - invoice.paid_count
        invoice.collected_percent = _percent(invoice.collected_amount, invoice.expected_amount)
        invoice.is_overdue = (
            not invoice.is_draft and invoice.due_date < today and invoice.paid_count < invoice.lines_count
        )
    latest_invoice = recent_invoices[0] if recent_invoices else None

    # Customers with the most unpaid receipts.
    debtors = (
        Customer.objects.annotate(
            pending_count=Count("lines__invoiceline", filter=Q(lines__invoiceline__isPaid=False)),
            pending_amount=Sum("lines__invoiceline__amount", filter=Q(lines__invoiceline__isPaid=False)),
        )
        .filter(pending_count__gt=0)
        .order_by("-pending_amount", "-pending_count", "lastName")[:5]
    )

    lines_by_location = list(
        Line.objects.filter(isActive=True)
        .values("location__name")
        .annotate(total=Count("id"))
        .order_by("-total", "location__name")
    )
    lines_by_fee = list(
        Line.objects.filter(isActive=True)
        .values("fee__name", "fee__amount")
        .annotate(total=Count("id"))
        .order_by("-total", "fee__name")
    )
    for row in lines_by_location + lines_by_fee:
        row["percent"] = _percent(row["total"], line_counts["active"])

    return {
        "today": today,
        "customers_total": customers_total,
        "customers_without_lines": customers_without_lines,
        "lines_total": line_counts["total"],
        "lines_active": line_counts["active"],
        "lines_inactive": line_counts["total"] - line_counts["active"],
        "lines_active_without_fee": line_counts["active_without_fee"],
        "pending_count": pending["count"],
        "pending_amount": pending["amount"] or 0,
        "overdue_count": overdue["count"],
        "overdue_amount": overdue["amount"] or 0,
        "latest_invoice": latest_invoice,
        "recent_invoices": recent_invoices,
        "debtors": debtors,
        "lines_by_location": lines_by_location,
        "lines_by_fee": lines_by_fee,
    }


@login_required(login_url='login')
def home_view(request):
    return render(request, 'home.html', _dashboard_context())

def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")  # change to your home url name

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("home")  # change to your home url name
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "registration/login.html")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")