from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from shell.htmx import messages_response
from shell.pagination import paginate

from . import services
from .forms import FeeForm, InvoiceForm, InvoiceLineAssignForm, InvoiceLineLateFeeForm, LateFeeForm
from .models import Fee, Invoice, InvoiceLine, LateFee


@login_required(login_url="login")
def fee_home(request):
    query = request.GET.get("q", "").strip()
    page_obj = paginate(request, services.search_fees(query))
    context = {"fees": page_obj.object_list, "page_obj": page_obj, "query": query}
    if request.htmx:
        return render(request, "partials/fee/_fee_table.html", context)
    context["late_fees"] = services.list_late_fees()
    return render(request, "fee_home.html", context)


@login_required(login_url="login")
def late_fee_table(request):
    return render(request, "partials/late_fee/_late_fee_table.html", {"late_fees": services.list_late_fees()})


def _late_fee_saved_response(request):
    return messages_response(request, "lateFeeSaved")


@login_required(login_url="login")
def late_fee_create(request):
    if request.method == "POST":
        form = LateFeeForm(request.POST)
        if form.is_valid():
            services.create_late_fee(form.save(commit=False), request.user, form.cleaned_data["make_default"])
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
    messages.success(request, f"La mora «{late_fee.name}» ahora es la mora por defecto.")
    return _late_fee_saved_response(request)


@login_required(login_url="login")
def fee_create(request):
    if request.method == "POST":
        form = FeeForm(request.POST)
        if form.is_valid():
            services.create_fee(form.save(commit=False), request.user)
            messages.success(request, "Cuota creada correctamente.")
            return messages_response(request, "feeSaved")

        return render(request, "partials/fee/_fee_form_modal.html", {"form": form})

    form = FeeForm()
    return render(request, "partials/fee/_fee_form_modal.html", {"form": form})


@login_required(login_url="login")
@require_POST
def fee_toggle(request, pk):
    fee = services.toggle_fee(get_object_or_404(Fee, pk=pk))
    messages.success(request, "Cuota activada correctamente." if fee.isActive else "Cuota desactivada correctamente.")
    return messages_response(request, "feeSaved")


@login_required(login_url="login")
def billing_home(request):
    query = request.GET.get("q", "").strip()
    page_obj = paginate(request, services.search_invoices(query))
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
            services.save_invoice(form.save(commit=False), request.user)
            messages.success(
                request,
                "Factura creada correctamente." if is_new else "Factura actualizada correctamente.",
            )
            return messages_response(request, "invoiceSaved")
    else:
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
    # Las acciones de cada recibo dependen del estado de la factura, así que se refrescan ambas partes.
    return messages_response(request, "invoiceSaved, invoiceLinesChanged")


def _invoice_status_action(request, pk, action):
    # GET muestra el modal de confirmación; POST abre o cierra la factura.
    invoice = get_object_or_404(Invoice.objects.select_related("account"), pk=pk)
    if request.method != "POST":
        return render(
            request,
            "partials/invoice/_invoice_status_modal.html",
            {"invoice": invoice, "action": action, **services.invoice_summary(invoice)},
        )
    try:
        getattr(invoice, action)()
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        if action == "open":
            messages.success(request, f"{invoice.title} abierta. Ya se pueden registrar pagos.")
        else:
            messages.success(request, f"{invoice.title} cerrada. Los recibos sin pagar quedaron vencidos.")
    return _invoice_status_changed_response(request)


@login_required(login_url="login")
def invoice_open(request, pk):
    return _invoice_status_action(request, pk, "open")


@login_required(login_url="login")
def invoice_close(request, pk):
    return _invoice_status_action(request, pk, "close")


def _invoice_lines_filters(request):
    return request.GET.get("q", "").strip(), request.GET.get("status", "")


def _invoice_lines_changed_response(request):
    return messages_response(request, "invoiceLinesChanged")


@login_required(login_url="login")
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("account", "created_by"), pk=pk)
    query, status = _invoice_lines_filters(request)
    page_obj = paginate(request, services.search_invoice_lines(invoice, query, status))
    context = {
        "invoice": invoice,
        "invoice_lines": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
        "status": status,
        **services.invoice_summary(invoice),
    }
    return render(request, "invoice_detail.html", context)


@login_required(login_url="login")
def invoice_summary(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("account", "created_by"), pk=pk)
    context = {"invoice": invoice, **services.invoice_summary(invoice)}
    return render(request, "partials/invoice/_invoice_summary.html", context)


@login_required(login_url="login")
def invoice_lines(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    query, status = _invoice_lines_filters(request)
    page_obj = paginate(request, services.search_invoice_lines(invoice, query, status))
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
    unassigned = services.unassigned_counts(invoice)
    return render(
        request,
        "partials/invoice/_invoice_assign_confirm_modal.html",
        {
            "invoice": invoice,
            "pending_count": unassigned["with_fee"],
            "without_fee_count": unassigned["without_fee"],
        },
    )


@login_required(login_url="login")
@require_POST
def invoice_assign_lines(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    try:
        created_count, without_fee_count = services.assign_all_lines(invoice, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return _invoice_lines_changed_response(request)

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
    blocked_reason = services.assign_blocked_reason(invoice)
    if blocked_reason:
        messages.error(request, blocked_reason)
        return _invoice_lines_changed_response(request)

    if request.method == "POST":
        form = InvoiceLineAssignForm(request.POST, invoice=invoice)
        if form.is_valid():
            line = form.cleaned_data["line"]
            services.assign_line(invoice, line, request.user)
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
    try:
        services.toggle_invoice_line_paid(invoice_line)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(
            request,
            f"Línea {invoice_line.line.code} marcada como {'pagada' if invoice_line.isPaid else 'pendiente'}.",
        )
    return _invoice_lines_changed_response(request)


@login_required(login_url="login")
def invoice_line_late_fee(request, pk):
    invoice_line = get_object_or_404(InvoiceLine.objects.select_related("invoice", "line", "late_fee"), pk=pk)
    try:
        services.ensure_late_fee_editable(invoice_line)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return _invoice_lines_changed_response(request)

    if request.method == "POST":
        form = InvoiceLineLateFeeForm(request.POST)
        if form.is_valid():
            services.change_late_fee(invoice_line, form.cleaned_data["late_fee"])
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
    try:
        services.remove_invoice_line(invoice_line)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f"Línea {invoice_line.line.code} quitada de la factura.")
    return _invoice_lines_changed_response(request)


def _receipts_pdf_response(request, invoice, invoice_lines, filename):
    if not invoice_lines:
        messages.info(request, "Esta factura todavía no tiene líneas asignadas para imprimir.")
        return redirect("invoice_detail", pk=invoice.pk)

    pdf = services.receipts_pdf(invoice, invoice_lines, "invoice_receipts_pdf_landscape.html")
    if pdf is None:
        messages.error(request, "Ocurrió un error al generar los recibos en PDF.")
        return redirect("invoice_detail", pk=invoice.pk)

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@login_required(login_url="login")
def invoice_print_receipts_landscape(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("account"), pk=pk)
    filename = f"recibos_{invoice.start_date:%d-%m-%Y}_al_{invoice.end_date:%d-%m-%Y}_horizontal.pdf"
    return _receipts_pdf_response(request, invoice, services.printable_receipts(invoice), filename)


@login_required(login_url="login")
def invoice_print_select(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    return render(
        request,
        "partials/invoice/_invoice_print_select_modal.html",
        {"invoice": invoice, "invoice_lines": services.receipts_for_selection(invoice)},
    )


@login_required(login_url="login")
def invoice_print_selected(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("account"), pk=pk)
    lines = services.receipts_for_selection(invoice, request.GET.getlist("ids"))
    filename = f"recibos_seleccionados_{invoice.start_date:%d-%m-%Y}_al_{invoice.end_date:%d-%m-%Y}.pdf"
    return _receipts_pdf_response(request, invoice, lines, filename)


@login_required(login_url="login")
def invoice_line_print_receipt(request, pk):
    invoice_line = get_object_or_404(
        InvoiceLine.objects.select_related(
            "invoice__account", "line__customer", "line__location", "fee", "late_fee", "carried_to"
        ),
        pk=pk,
    )
    filename = f"recibo_{invoice_line.code}.pdf"
    return _receipts_pdf_response(request, invoice_line.invoice, [invoice_line], filename)
