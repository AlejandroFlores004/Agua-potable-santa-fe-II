import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from xhtml2pdf import pisa

from connection.models import Line

from .forms import FeeForm, InvoiceForm
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
        Invoice.objects.select_related("fee", "created_by")
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
    response = render(request, "partials/invoice/_form_success_oob.html")
    response["HX-Trigger"] = "invoiceSaved"
    return response


@login_required(login_url="login")
def invoice_assign_lines_confirm(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    assigned_line_ids = InvoiceLine.objects.filter(invoice=invoice).values_list("line_id", flat=True)
    pending_count = Line.objects.exclude(id__in=assigned_line_ids).count()
    return render(
        request,
        "partials/invoice/_invoice_assign_confirm_modal.html",
        {"invoice": invoice, "pending_count": pending_count},
    )


@login_required(login_url="login")
@require_POST
def invoice_assign_lines(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    assigned_line_ids = InvoiceLine.objects.filter(invoice=invoice).values_list("line_id", flat=True)
    lines_to_assign = Line.objects.exclude(id__in=assigned_line_ids)

    created_count = 0
    for line in lines_to_assign:
        # InvoiceLine.save() re-saves itself to generate `code`, so it must be
        # created via a plain save() rather than objects.create() (which forces
        # an INSERT on both saves and raises a duplicate-pk IntegrityError).
        InvoiceLine(invoice=invoice, line=line, created_by=request.user).save()
        created_count += 1

    if created_count:
        messages.success(request, f"{created_count} línea(s) asignada(s) a la factura.")
    else:
        messages.info(request, "Todas las líneas ya estaban asignadas a esta factura.")

    response = render(request, "partials/invoice/_form_success_oob.html")
    response["HX-Trigger"] = "invoiceSaved"
    return response


@login_required(login_url="login")
def invoice_lines(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    lines = (
        InvoiceLine.objects.filter(invoice=invoice)
        .select_related("line", "line__customer")
        .order_by("line__code")
    )
    return render(
        request,
        "partials/invoice/_invoice_lines_modal.html",
        {"invoice": invoice, "invoice_lines": lines},
    )


@login_required(login_url="login")
def invoice_print_receipts(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    lines = (
        InvoiceLine.objects.filter(invoice=invoice)
        .select_related("line", "line__customer")
        .order_by("line__code")
    )

    if not lines:
        messages.info(request, "Esta factura todavía no tiene líneas asignadas para imprimir.")
        return redirect("billing_home")

    html = render_to_string(
        "invoice_receipts_pdf.html",
        {"invoice": invoice, "invoice_lines": lines},
    )

    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=buffer)
    if pisa_status.err:
        messages.error(request, "Ocurrió un error al generar los recibos en PDF.")
        return redirect("billing_home")

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="recibos_factura_{invoice.pk}.pdf"'
    return response


@login_required(login_url="login")
def invoice_print_receipts_landscape(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    lines = (
        InvoiceLine.objects.filter(invoice=invoice)
        .select_related("line", "line__customer", "line__location")
        .order_by("line__code")
    )

    if not lines:
        messages.info(request, "Esta factura todavía no tiene líneas asignadas para imprimir.")
        return redirect("billing_home")

    html = render_to_string(
        "invoice_receipts_pdf_landscape.html",
        {"invoice": invoice, "invoice_lines": lines},
    )

    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=buffer)
    if pisa_status.err:
        messages.error(request, "Ocurrió un error al generar los recibos en PDF.")
        return redirect("billing_home")

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="recibos_factura_{invoice.pk}_horizontal.pdf"'
    return response
