import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from xhtml2pdf import pisa

from connection.models import Line

from .forms import FeeForm, InvoiceForm, InvoiceLineAssignForm
from .models import Fee, Invoice, InvoiceLine


def _get_fees(request):
    fees = Fee.objects.select_related("created_by").order_by("-created_at")
    query = request.GET.get("q", "").strip()
    if query:
        fees = fees.filter(name__icontains=query)
    return fees, query


@login_required(login_url="login")
def fee_home(request):
    fees, query = _get_fees(request)
    context = {"fees": fees, "query": query}
    if request.htmx:
        return render(request, "partials/fee/_fee_table.html", context)
    return render(request, "fee_home.html", context)


@login_required(login_url="login")
def fee_create(request):
    if request.method == "POST":
        form = FeeForm(request.POST)
        if form.is_valid():
            fee = form.save(commit=False)
            fee.created_by = request.user
            fee.save()

            messages.success(request, "Cuota creada correctamente.")
            response = render(request, "partials/fee/_form_success_oob.html")
            response["HX-Trigger"] = "feeSaved"
            return response

        return render(request, "partials/fee/_fee_form_modal.html", {"form": form})

    form = FeeForm()
    return render(request, "partials/fee/_fee_form_modal.html", {"form": form})


@login_required(login_url="login")
@require_POST
def fee_delete(request, pk):
    fee = get_object_or_404(Fee, pk=pk)
    fee.delete()
    messages.success(request, "Cuota eliminada correctamente.")
    response = render(request, "partials/fee/_form_success_oob.html")
    response["HX-Trigger"] = "feeSaved"
    return response


def _get_invoices(request):
    invoices = (
        Invoice.objects.select_related("fee", "account", "created_by")
        .annotate(
            lines_count=Count("invoiceline", distinct=True),
            paid_count=Count("invoiceline", filter=Q(invoiceline__isPaid=True), distinct=True),
        )
        .order_by("-created_at")
    )
    query = request.GET.get("q", "").strip()
    if query:
        invoices = invoices.filter(fee__name__icontains=query)
    return invoices, query


@login_required(login_url="login")
def billing_home(request):
    invoices, query = _get_invoices(request)
    context = {"invoices": invoices, "query": query}
    if request.htmx:
        return render(request, "partials/invoice/_invoice_table.html", context)
    return render(request, "billing_home.html", context)


@login_required(login_url="login")
def invoice_form(request, pk=None):
    invoice = get_object_or_404(Invoice, pk=pk) if pk else Invoice()
    is_new = invoice.pk is None

    if request.method == "POST":
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            invoice = form.save(commit=False)
            if is_new:
                invoice.created_by = request.user
            invoice.save()

            messages.success(
                request,
                "Factura creada correctamente." if is_new else "Factura actualizada correctamente.",
            )
            response = render(request, "partials/invoice/_form_success_oob.html")
            response["HX-Trigger"] = "invoiceSaved"
            return response

        return render(
            request,
            "partials/invoice/_invoice_form_modal.html",
            {"form": form, "invoice": invoice, "is_new": is_new},
        )

    form = InvoiceForm(instance=invoice)
    return render(
        request,
        "partials/invoice/_invoice_form_modal.html",
        {"form": form, "invoice": invoice, "is_new": is_new},
    )


@login_required(login_url="login")
@require_POST
def invoice_delete(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    invoice.delete()
    messages.success(request, "Factura eliminada correctamente.")
    response = HttpResponse()
    response["HX-Redirect"] = reverse("billing_home")
    return response


def _get_invoice_summary(invoice):
    counts = InvoiceLine.objects.filter(invoice=invoice).aggregate(
        lines_count=Count("id"),
        paid_count=Count("id", filter=Q(isPaid=True)),
    )
    lines_count = counts["lines_count"]
    paid_count = counts["paid_count"]
    assigned_line_ids = InvoiceLine.objects.filter(invoice=invoice).values_list("line_id", flat=True)
    return {
        "lines_count": lines_count,
        "paid_count": paid_count,
        "pending_count": lines_count - paid_count,
        "paid_percent": round(paid_count * 100 / lines_count) if lines_count else 0,
        "expected_amount": invoice.fee.amount * lines_count,
        "collected_amount": invoice.fee.amount * paid_count,
        "unassigned_active_count": Line.objects.filter(isActive=True).exclude(id__in=assigned_line_ids).count(),
    }


def _get_invoice_lines(request, invoice):
    invoice_lines = (
        InvoiceLine.objects.filter(invoice=invoice)
        .select_related("line", "line__customer", "line__location")
        .order_by("line__code")
    )
    query = request.GET.get("q", "").strip()
    if query:
        invoice_lines = invoice_lines.filter(
            Q(code__icontains=query)
            | Q(line__code__icontains=query)
            | Q(line__location__name__icontains=query)
            | Q(line__customer__firstName__icontains=query)
            | Q(line__customer__lastName__icontains=query)
        )
    status = request.GET.get("status", "")
    if status == "paid":
        invoice_lines = invoice_lines.filter(isPaid=True)
    elif status == "pending":
        invoice_lines = invoice_lines.filter(isPaid=False)
    return invoice_lines, query, status


def _invoice_lines_changed_response(request):
    response = render(request, "partials/invoice/_form_success_oob.html")
    response["HX-Trigger"] = "invoiceLinesChanged"
    return response


@login_required(login_url="login")
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("fee", "account", "created_by"), pk=pk)
    invoice_lines, query, status = _get_invoice_lines(request, invoice)
    context = {
        "invoice": invoice,
        "invoice_lines": invoice_lines,
        "query": query,
        "status": status,
        **_get_invoice_summary(invoice),
    }
    return render(request, "invoice_detail.html", context)


@login_required(login_url="login")
def invoice_summary(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("fee", "account", "created_by"), pk=pk)
    context = {"invoice": invoice, **_get_invoice_summary(invoice)}
    return render(request, "partials/invoice/_invoice_summary.html", context)


@login_required(login_url="login")
def invoice_lines(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("fee"), pk=pk)
    invoice_lines, query, status = _get_invoice_lines(request, invoice)
    return render(
        request,
        "partials/invoice/_invoice_lines_table.html",
        {"invoice": invoice, "invoice_lines": invoice_lines, "query": query, "status": status},
    )


def _unassigned_active_lines(invoice):
    assigned_line_ids = InvoiceLine.objects.filter(invoice=invoice).values_list("line_id", flat=True)
    return Line.objects.filter(isActive=True).exclude(id__in=assigned_line_ids)


@login_required(login_url="login")
def invoice_assign_lines_confirm(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    pending_count = _unassigned_active_lines(invoice).count()
    return render(
        request,
        "partials/invoice/_invoice_assign_confirm_modal.html",
        {"invoice": invoice, "pending_count": pending_count},
    )


@login_required(login_url="login")
@require_POST
def invoice_assign_lines(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    created_count = 0
    for line in _unassigned_active_lines(invoice):
        # InvoiceLine.save() re-saves itself to generate `code`, so it must be
        # created via a plain save() rather than objects.create() (which forces
        # an INSERT on both saves and raises a duplicate-pk IntegrityError).
        InvoiceLine(invoice=invoice, line=line, created_by=request.user).save()
        created_count += 1

    if created_count:
        messages.success(request, f"{created_count} línea(s) asignada(s) a la factura.")
    else:
        messages.info(request, "Todas las líneas activas ya estaban asignadas a esta factura.")

    return _invoice_lines_changed_response(request)


@login_required(login_url="login")
def invoice_assign_line(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    if request.method == "POST":
        form = InvoiceLineAssignForm(request.POST, invoice=invoice)
        if form.is_valid():
            line = form.cleaned_data["line"]
            InvoiceLine(invoice=invoice, line=line, created_by=request.user).save()
            messages.success(request, f"Línea {line.code} asignada a la factura.")
            return _invoice_lines_changed_response(request)
    else:
        form = InvoiceLineAssignForm(invoice=invoice)

    return render(
        request,
        "partials/invoice/_invoice_assign_line_modal.html",
        {"invoice": invoice, "form": form},
    )


@login_required(login_url="login")
@require_POST
def invoice_line_toggle_paid(request, pk):
    invoice_line = get_object_or_404(InvoiceLine.objects.select_related("line"), pk=pk)
    invoice_line.isPaid = not invoice_line.isPaid
    invoice_line.save(update_fields=["isPaid"])
    messages.success(
        request,
        f"Línea {invoice_line.line.code} marcada como {'pagada' if invoice_line.isPaid else 'pendiente'}.",
    )
    return _invoice_lines_changed_response(request)


@login_required(login_url="login")
@require_POST
def invoice_line_remove(request, pk):
    invoice_line = get_object_or_404(InvoiceLine.objects.select_related("line"), pk=pk)
    if invoice_line.isPaid:
        messages.error(request, "No se puede quitar una línea que ya está pagada.")
    else:
        invoice_line.delete()
        messages.success(request, f"Línea {invoice_line.line.code} quitada de la factura.")
    return _invoice_lines_changed_response(request)


def _render_receipts_pdf(request, invoice, invoice_lines, template_name, filename):
    if not invoice_lines:
        messages.info(request, "Esta factura todavía no tiene líneas asignadas para imprimir.")
        return redirect("invoice_detail", pk=invoice.pk)

    html = render_to_string(template_name, {"invoice": invoice, "invoice_lines": invoice_lines})

    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=buffer)
    if pisa_status.err:
        messages.error(request, "Ocurrió un error al generar los recibos en PDF.")
        return redirect("invoice_detail", pk=invoice.pk)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@login_required(login_url="login")
def invoice_print_receipts_landscape(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("fee", "account"), pk=pk)
    lines = (
        InvoiceLine.objects.filter(invoice=invoice)
        .select_related("line", "line__customer", "line__location")
        .order_by("line__code")
    )
    filename = f"recibos_{invoice.start_date:%d-%m-%Y}_al_{invoice.end_date:%d-%m-%Y}_horizontal.pdf"
    return _render_receipts_pdf(request, invoice, lines, "invoice_receipts_pdf_landscape.html", filename)


@login_required(login_url="login")
def invoice_print_select(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("fee"), pk=pk)
    invoice_lines = (
        InvoiceLine.objects.filter(invoice=invoice)
        .select_related("line", "line__customer", "line__location")
        .order_by("line__code")
    )
    return render(
        request,
        "partials/invoice/_invoice_print_select_modal.html",
        {"invoice": invoice, "invoice_lines": invoice_lines},
    )


@login_required(login_url="login")
def invoice_print_selected(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("fee", "account"), pk=pk)
    lines = (
        InvoiceLine.objects.filter(invoice=invoice, pk__in=request.GET.getlist("ids"))
        .select_related("line", "line__customer", "line__location")
        .order_by("line__code")
    )
    filename = f"recibos_seleccionados_{invoice.start_date:%d-%m-%Y}_al_{invoice.end_date:%d-%m-%Y}.pdf"
    return _render_receipts_pdf(request, invoice, lines, "invoice_receipts_pdf_landscape.html", filename)


@login_required(login_url="login")
def invoice_line_print_receipt(request, pk):
    invoice_line = get_object_or_404(
        InvoiceLine.objects.select_related("invoice__fee", "invoice__account", "line__customer", "line__location"),
        pk=pk,
    )
    filename = f"recibo_{invoice_line.code}.pdf"
    return _render_receipts_pdf(
        request, invoice_line.invoice, [invoice_line], "invoice_receipts_pdf_landscape.html", filename
    )
