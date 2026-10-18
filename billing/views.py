import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from xhtml2pdf import pisa

from connection.models import Line
from shell.pagination import paginate

from .forms import FeeForm, InvoiceForm, InvoiceLineAssignForm, InvoiceLineLateFeeForm, LateFeeForm
from .models import Fee, Invoice, InvoiceLine, LateFee

LINE_TOTAL = F("amount") + F("previous_balance") + F("late_fee_amount")


def _get_fees(request):
    fees = Fee.objects.select_related("created_by").order_by("-created_at")
    query = request.GET.get("q", "").strip()
    if query:
        fees = fees.filter(name__icontains=query)
    return fees, query


@login_required(login_url="login")
def fee_home(request):
    fees, query = _get_fees(request)
    page_obj = paginate(request, fees)
    context = {"fees": page_obj.object_list, "page_obj": page_obj, "query": query}
    if request.htmx:
        return render(request, "partials/fee/_fee_table.html", context)
    context["late_fees"] = _get_late_fees()
    return render(request, "fee_home.html", context)


def _get_late_fees():
    return LateFee.objects.select_related("created_by").order_by("-isDefault", "-created_at")


@login_required(login_url="login")
def late_fee_table(request):
    return render(request, "partials/late_fee/_late_fee_table.html", {"late_fees": _get_late_fees()})


def _late_fee_saved_response(request):
    response = render(request, "partials/fee/_form_success_oob.html")
    response["HX-Trigger"] = "lateFeeSaved"
    return response


@login_required(login_url="login")
def late_fee_create(request):
    if request.method == "POST":
        form = LateFeeForm(request.POST)
        if form.is_valid():
            late_fee = form.save(commit=False)
            late_fee.created_by = request.user
            late_fee.save()
            # La primera mora siempre queda por defecto para que los recibos atrasados la cobren.
            if form.cleaned_data["make_default"] or not LateFee.get_default():
                late_fee.make_default()

            messages.success(request, "Mora creada correctamente.")
            return _late_fee_saved_response(request)

        return render(request, "partials/late_fee/_late_fee_form_modal.html", {"form": form})

    form = LateFeeForm()
    return render(request, "partials/late_fee/_late_fee_form_modal.html", {"form": form})


@login_required(login_url="login")
@require_POST
def late_fee_make_default(request, pk):
    late_fee = get_object_or_404(LateFee, pk=pk)
    late_fee.make_default()
    messages.success(request, f"La mora \"{late_fee.name}\" ahora es la mora por defecto.")
    return _late_fee_saved_response(request)


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
def fee_toggle(request, pk):
    # Las cuotas no se eliminan (las usan líneas y recibos); solo se activan o desactivan.
    fee = get_object_or_404(Fee, pk=pk)
    fee.isActive = not fee.isActive
    fee.save(update_fields=["isActive"])
    messages.success(request, "Cuota activada correctamente." if fee.isActive else "Cuota desactivada correctamente.")
    response = render(request, "partials/fee/_form_success_oob.html")
    response["HX-Trigger"] = "feeSaved"
    return response


def _get_invoices(request):
    invoices = (
        Invoice.objects.select_related("account", "created_by")
        .annotate(
            lines_count=Count("invoiceline", distinct=True),
            paid_count=Count("invoiceline", filter=Q(invoiceline__isPaid=True), distinct=True),
        )
        .order_by("-created_at")
    )
    query = request.GET.get("q", "").strip()
    if query:
        invoices = invoices.filter(
            Q(account__name__icontains=query) | Q(account__number__icontains=query)
        )
    return invoices, query


@login_required(login_url="login")
def billing_home(request):
    invoices, query = _get_invoices(request)
    page_obj = paginate(request, invoices)
    context = {"invoices": page_obj.object_list, "page_obj": page_obj, "query": query}
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


def _invoice_status_changed_response(request):
    response = render(request, "partials/invoice/_form_success_oob.html")
    # Las acciones de cada recibo dependen del estado de la factura, así que se refrescan ambas partes.
    response["HX-Trigger"] = "invoiceSaved, invoiceLinesChanged"
    return response


@login_required(login_url="login")
@require_POST
def invoice_open(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    try:
        invoice.open()
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f"{invoice.title} abierta. Ya se pueden registrar pagos.")
    return _invoice_status_changed_response(request)


@login_required(login_url="login")
@require_POST
def invoice_close(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    try:
        invoice.close()
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f"{invoice.title} cerrada.")
    return _invoice_status_changed_response(request)


def _assign_blocked_reason(invoice):
    if invoice.is_closed:
        return "La factura está cerrada; ya no se le pueden asignar líneas."
    # Asignar trasladaría al borrador los recibos sin pagar de la factura abierta,
    # y ahí ya no podrían cobrarse hasta abrir este borrador.
    open_invoice = Invoice.get_open() if invoice.is_draft else None
    if open_invoice:
        return f"Cierra la {open_invoice.title.lower()} antes de asignar líneas a este borrador."
    return None


def _unassigned_active_lines(invoice):
    assigned_line_ids = InvoiceLine.objects.filter(invoice=invoice).values_list("line_id", flat=True)
    return Line.objects.filter(isActive=True).exclude(id__in=assigned_line_ids)


def _get_invoice_summary(invoice):
    # Los recibos trasladados no cuentan como esperados ni pendientes aquí: su saldo
    # ya se cobra en el recibo posterior que los absorbió.
    not_carried = Q(carried_to__isnull=True)
    counts = InvoiceLine.objects.filter(invoice=invoice).aggregate(
        lines_count=Count("id"),
        paid_count=Count("id", filter=Q(isPaid=True)),
        carried_count=Count("id", filter=Q(carried_to__isnull=False)),
        expected_amount=Sum(LINE_TOTAL, filter=not_carried),
        collected_amount=Sum(LINE_TOTAL, filter=Q(isPaid=True)),
    )
    lines_count = counts["lines_count"]
    paid_count = counts["paid_count"]
    carried_count = counts["carried_count"]
    unassigned_active = _unassigned_active_lines(invoice)
    return {
        "assign_blocked_reason": _assign_blocked_reason(invoice),
        "other_open_invoice": Invoice.objects.filter(status=Invoice.Status.OPEN).exclude(pk=invoice.pk).first(),
        "lines_count": lines_count,
        "paid_count": paid_count,
        "carried_count": carried_count,
        "pending_count": lines_count - paid_count - carried_count,
        "paid_percent": round(paid_count * 100 / lines_count) if lines_count else 0,
        "expected_amount": counts["expected_amount"] or 0,
        "collected_amount": counts["collected_amount"] or 0,
        "unassigned_active_count": unassigned_active.filter(fee__isnull=False).count(),
        "unassigned_without_fee_count": unassigned_active.filter(fee__isnull=True).count(),
    }


def _get_invoice_lines(request, invoice):
    invoice_lines = (
        InvoiceLine.objects.filter(invoice=invoice)
        .select_related("line", "line__customer", "line__location", "fee", "late_fee", "carried_to")
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
        invoice_lines = invoice_lines.filter(isPaid=False, carried_to__isnull=True)
    elif status == "carried":
        invoice_lines = invoice_lines.filter(carried_to__isnull=False)
    return invoice_lines, query, status


def _invoice_lines_changed_response(request):
    response = render(request, "partials/invoice/_form_success_oob.html")
    response["HX-Trigger"] = "invoiceLinesChanged"
    return response


@login_required(login_url="login")
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("account", "created_by"), pk=pk)
    invoice_lines, query, status = _get_invoice_lines(request, invoice)
    page_obj = paginate(request, invoice_lines)
    context = {
        "invoice": invoice,
        "invoice_lines": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
        "status": status,
        **_get_invoice_summary(invoice),
    }
    return render(request, "invoice_detail.html", context)


@login_required(login_url="login")
def invoice_summary(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("account", "created_by"), pk=pk)
    context = {"invoice": invoice, **_get_invoice_summary(invoice)}
    return render(request, "partials/invoice/_invoice_summary.html", context)


@login_required(login_url="login")
def invoice_lines(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    invoice_lines, query, status = _get_invoice_lines(request, invoice)
    page_obj = paginate(request, invoice_lines)
    return render(
        request,
        "partials/invoice/_invoice_lines_table.html",
        {
            "invoice": invoice,
            "invoice_lines": page_obj.object_list,
            "page_obj": page_obj,
            "query": query,
            "status": status,
        },
    )


@login_required(login_url="login")
def invoice_assign_lines_confirm(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    unassigned_active = _unassigned_active_lines(invoice)
    return render(
        request,
        "partials/invoice/_invoice_assign_confirm_modal.html",
        {
            "invoice": invoice,
            "pending_count": unassigned_active.filter(fee__isnull=False).count(),
            "without_fee_count": unassigned_active.filter(fee__isnull=True).count(),
        },
    )


@login_required(login_url="login")
@require_POST
def invoice_assign_lines(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    blocked_reason = _assign_blocked_reason(invoice)
    if blocked_reason:
        messages.error(request, blocked_reason)
        return _invoice_lines_changed_response(request)

    unassigned_active = _unassigned_active_lines(invoice)
    without_fee_count = unassigned_active.filter(fee__isnull=True).count()
    created_count = 0
    for line in unassigned_active.filter(fee__isnull=False).select_related("fee"):
        # InvoiceLine.save() re-saves itself to generate `code`, so it must be
        # created via a plain save() rather than objects.create() (which forces
        # an INSERT on both saves and raises a duplicate-pk IntegrityError).
        InvoiceLine(invoice=invoice, line=line, created_by=request.user).save()
        created_count += 1

    if created_count:
        messages.success(request, f"{created_count} línea(s) asignada(s) a la factura.")
    else:
        messages.info(request, "Todas las líneas activas con cuota ya estaban asignadas a esta factura.")
    if without_fee_count:
        messages.warning(
            request, f"{without_fee_count} línea(s) activa(s) sin cuota no se asignaron. Asígnales una cuota primero."
        )

    return _invoice_lines_changed_response(request)


@login_required(login_url="login")
def invoice_assign_line(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    blocked_reason = _assign_blocked_reason(invoice)
    if blocked_reason:
        messages.error(request, blocked_reason)
        return _invoice_lines_changed_response(request)

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
    invoice_line = get_object_or_404(InvoiceLine.objects.select_related("invoice", "line", "carried_to"), pk=pk)
    if invoice_line.invoice.is_draft:
        messages.error(request, "La factura sigue en borrador; ábrela para poder registrar pagos.")
        return _invoice_lines_changed_response(request)
    if invoice_line.is_carried:
        messages.error(
            request,
            f"El saldo de este recibo se trasladó al recibo {invoice_line.carried_to.code}; cóbralo en ese recibo.",
        )
        return _invoice_lines_changed_response(request)
    invoice_line.isPaid = not invoice_line.isPaid
    invoice_line.save(update_fields=["isPaid"])
    messages.success(
        request,
        f"Línea {invoice_line.line.code} marcada como {'pagada' if invoice_line.isPaid else 'pendiente'}.",
    )
    return _invoice_lines_changed_response(request)


@login_required(login_url="login")
def invoice_line_late_fee(request, pk):
    invoice_line = get_object_or_404(InvoiceLine.objects.select_related("invoice", "line", "late_fee"), pk=pk)
    # Un recibo pagado o ya trasladado está cerrado: cambiar su mora descuadraría lo cobrado.
    if invoice_line.isPaid or invoice_line.is_carried or invoice_line.invoice.is_closed:
        messages.error(request, "Solo se puede cambiar la mora de un recibo pendiente.")
        return _invoice_lines_changed_response(request)

    if request.method == "POST":
        form = InvoiceLineLateFeeForm(request.POST)
        if form.is_valid():
            invoice_line.set_late_fee(form.cleaned_data["late_fee"])
            invoice_line.save(update_fields=["late_fee", "late_fee_amount"])
            messages.success(request, f"Mora del recibo {invoice_line.code} actualizada.")
            return _invoice_lines_changed_response(request)
    else:
        form = InvoiceLineLateFeeForm(initial={"late_fee": invoice_line.late_fee})

    return render(
        request,
        "partials/invoice/_invoice_line_late_fee_modal.html",
        {"invoice_line": invoice_line, "form": form},
    )


@login_required(login_url="login")
@require_POST
def invoice_line_remove(request, pk):
    invoice_line = get_object_or_404(InvoiceLine.objects.select_related("invoice", "line"), pk=pk)
    if invoice_line.invoice.is_closed:
        messages.error(request, "No se pueden quitar líneas de una factura cerrada.")
    elif invoice_line.isPaid:
        messages.error(request, "No se puede quitar una línea que ya está pagada.")
    elif invoice_line.is_carried:
        messages.error(request, "No se puede quitar un recibo cuyo saldo ya se trasladó a un recibo posterior.")
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
    invoice = get_object_or_404(Invoice.objects.select_related("account"), pk=pk)
    # Los recibos trasladados no se imprimen: su saldo ya va en el recibo posterior.
    lines = (
        InvoiceLine.objects.filter(invoice=invoice, carried_to__isnull=True)
        .select_related("line", "line__customer", "line__location")
        .order_by("line__code")
    )
    filename = f"recibos_{invoice.start_date:%d-%m-%Y}_al_{invoice.end_date:%d-%m-%Y}_horizontal.pdf"
    return _render_receipts_pdf(request, invoice, lines, "invoice_receipts_pdf_landscape.html", filename)


@login_required(login_url="login")
def invoice_print_select(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    invoice_lines = (
        InvoiceLine.objects.filter(invoice=invoice)
        .select_related("line", "line__customer", "line__location", "carried_to")
        .order_by("line__code")
    )
    return render(
        request,
        "partials/invoice/_invoice_print_select_modal.html",
        {"invoice": invoice, "invoice_lines": invoice_lines},
    )


@login_required(login_url="login")
def invoice_print_selected(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("account"), pk=pk)
    lines = (
        InvoiceLine.objects.filter(invoice=invoice, pk__in=request.GET.getlist("ids"))
        .select_related("line", "line__customer", "line__location", "carried_to")
        .order_by("line__code")
    )
    filename = f"recibos_seleccionados_{invoice.start_date:%d-%m-%Y}_al_{invoice.end_date:%d-%m-%Y}.pdf"
    return _render_receipts_pdf(request, invoice, lines, "invoice_receipts_pdf_landscape.html", filename)


@login_required(login_url="login")
def invoice_line_print_receipt(request, pk):
    invoice_line = get_object_or_404(
        InvoiceLine.objects.select_related(
            "invoice__account", "line__customer", "line__location", "fee", "late_fee", "carried_to"
        ),
        pk=pk,
    )
    filename = f"recibo_{invoice_line.code}.pdf"
    return _render_receipts_pdf(
        request, invoice_line.invoice, [invoice_line], "invoice_receipts_pdf_landscape.html", filename
    )
