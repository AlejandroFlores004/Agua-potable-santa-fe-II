import io
from decimal import Decimal

from django.db.models import Prefetch, Q
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from billing.models import Fee, Invoice, InvoiceLine
from connection.models import Line, Location
from customer.models import Customer

# Por ahora la descripción de la mecha se usa como campo de observaciones.
WITH_OBSERVATIONS = ~Q(description__isnull=True) & ~Q(description__exact="")

LINE_STATUSES = {"active": "Activas", "inactive": "Inactivas", "all": "Todas"}


def render_pdf(template_name, context):
    """Genera un PDF desde una plantilla. Devuelve los bytes o None si xhtml2pdf falla."""
    html = render_to_string(template_name, {**context, "generated_at": timezone.localtime()})
    buffer = io.BytesIO()
    if pisa.CreatePDF(html, dest=buffer, encoding="utf-8").err:
        return None
    return buffer.getvalue()


def receipt_status(invoice_line):
    # Mismo criterio que la tabla de recibos de la factura.
    if invoice_line.isPaid:
        return "Pagado"
    if invoice_line.is_carried:
        return "Trasladado"
    if invoice_line.invoice.is_closed:
        return "Vencido"
    return "Pendiente"


def _with_status(invoice_lines):
    invoice_lines = list(invoice_lines)
    for invoice_line in invoice_lines:
        invoice_line.status_label = receipt_status(invoice_line)
    return invoice_lines


def _pending_receipts():
    # Un recibo trasladado ya está sumado en el saldo anterior del que lo absorbió,
    # así que la deuda real son los impagos sin trasladar.
    return InvoiceLine.objects.filter(isPaid=False, carried_to__isnull=True)


def customers_report():
    return {
        "customers": Customer.objects.prefetch_related("lines").order_by("firstName", "lastName"),
    }


def customer_observations_report():
    observed_lines = Line.objects.filter(WITH_OBSERVATIONS).select_related("location").order_by("code")
    customers = (
        Customer.objects.filter(lines__in=observed_lines)
        .distinct()
        .prefetch_related(Prefetch("lines", queryset=observed_lines, to_attr="observed_lines"))
        .order_by("firstName", "lastName")
    )
    return {"customers": customers, "lines_count": observed_lines.count()}


def customer_statement(customer):
    lines = customer.lines.select_related("location", "fee").order_by("code")
    receipts = _with_status(
        InvoiceLine.objects.filter(line__customer=customer)
        .select_related("invoice", "line", "carried_to")
        .order_by("-invoice__start_date", "line__code")
    )
    pending = [receipt for receipt in receipts if receipt.status_label in ("Pendiente", "Vencido")]
    return {
        "customer": customer,
        "lines": lines,
        "receipts": receipts,
        "pending_total": sum((receipt.total for receipt in pending), Decimal("0")),
        "overdue_total": sum(
            (receipt.total for receipt in pending if receipt.status_label == "Vencido"), Decimal("0")
        ),
    }


def lines_report(status="active", location_id="", fee_id=""):
    lines = Line.objects.select_related("customer", "location", "fee").order_by(
        "location__name", "code"
    )
    filters = []
    if status == "active":
        lines = lines.filter(isActive=True)
    elif status == "inactive":
        lines = lines.filter(isActive=False)
    filters.append(f"Estado: {LINE_STATUSES.get(status, LINE_STATUSES['all'])}")

    if location_id == "none":
        lines = lines.filter(location__isnull=True)
        filters.append("Ubicación: sin ubicación")
    elif location_id:
        location = Location.objects.filter(pk=location_id).first()
        if location:
            lines = lines.filter(location=location)
            filters.append(f"Ubicación: {location}")

    if fee_id:
        fee = Fee.objects.filter(pk=fee_id).first()
        if fee:
            lines = lines.filter(fee=fee)
            filters.append(f"Cuota: {fee.name}")

    lines = list(lines)
    return {
        "lines": lines,
        "filters": filters,
        "monthly_total": sum((line.fee.amount for line in lines if line.isActive and line.fee), Decimal("0")),
    }


def debtors_report(only_overdue=False):
    receipts = _pending_receipts()
    if only_overdue:
        receipts = receipts.filter(invoice__status=Invoice.Status.CLOSED)
    receipts = _with_status(
        receipts.select_related("invoice", "line", "line__customer", "line__location").order_by(
            "line__customer__firstName", "line__customer__lastName", "line__code", "invoice__start_date"
        )
    )

    debtors = {}
    for receipt in receipts:
        customer = receipt.line.customer
        debtor = debtors.setdefault(customer.pk, {"customer": customer, "receipts": [], "total": Decimal("0")})
        debtor["receipts"].append(receipt)
        debtor["total"] += receipt.total

    return {
        "debtors": list(debtors.values()),
        "only_overdue": only_overdue,
        "grand_total": sum((debtor["total"] for debtor in debtors.values()), Decimal("0")),
        "receipts_count": len(receipts),
    }


def report_form_options():
    return {
        "customers": Customer.objects.order_by("firstName", "lastName"),
        "locations": Location.objects.all(),
        "fees": Fee.objects.order_by("name"),
        "line_statuses": LINE_STATUSES,
        "observations_count": Customer.objects.filter(lines__in=Line.objects.filter(WITH_OBSERVATIONS))
        .distinct()
        .count(),
    }
