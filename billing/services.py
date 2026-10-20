import io

from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q, Sum
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from connection.models import Line

from .models import Fee, Invoice, InvoiceLine, LateFee

LINE_TOTAL = F("amount") + F("previous_balance") + F("late_fee_amount")


# ===== Cuotas y moras =====

def search_fees(query=""):
    fees = Fee.objects.select_related("created_by").order_by("-created_at")
    if query:
        fees = fees.filter(name__icontains=query)
    return fees


def list_late_fees():
    return LateFee.objects.select_related("created_by").order_by("-isDefault", "-created_at")


def create_late_fee(late_fee, user, make_default=False):
    late_fee.created_by = user
    late_fee.save()
    # La primera mora siempre queda por defecto para que los recibos atrasados la cobren.
    if make_default or not LateFee.get_default():
        late_fee.make_default()
    return late_fee


def create_fee(fee, user):
    fee.created_by = user
    fee.save()
    return fee


def toggle_fee(fee):
    # Las cuotas no se eliminan (las usan líneas y recibos); solo se activan o desactivan.
    fee.isActive = not fee.isActive
    fee.save(update_fields=["isActive"])
    return fee


# ===== Facturas =====

def search_invoices(query=""):
    invoices = (
        Invoice.objects.select_related("account", "created_by")
        .annotate(
            lines_count=Count("invoiceline", distinct=True),
            paid_count=Count("invoiceline", filter=Q(invoiceline__isPaid=True), distinct=True),
        )
        .order_by("-created_at")
    )
    if query:
        invoices = invoices.filter(
            Q(account__name__icontains=query) | Q(account__number__icontains=query)
        )
    return invoices


def save_invoice(invoice, user):
    if invoice.pk is None:
        invoice.created_by = user
    invoice.save()
    return invoice


def assign_blocked_reason(invoice):
    if invoice.is_closed:
        return "La factura está cerrada; ya no se le pueden asignar líneas."
    # Asignar trasladaría al borrador los recibos sin pagar de la factura abierta,
    # y ahí ya no podrían cobrarse hasta abrir este borrador.
    open_invoice = Invoice.get_open() if invoice.is_draft else None
    if open_invoice:
        return f"Cierra la {open_invoice.title.lower()} antes de asignar líneas a este borrador."
    return None


def unassigned_active_lines(invoice):
    assigned_line_ids = InvoiceLine.objects.filter(invoice=invoice).values_list("line_id", flat=True)
    return Line.objects.filter(isActive=True).exclude(id__in=assigned_line_ids)


def unassigned_counts(invoice):
    # Solo las líneas con cuota se pueden asignar; las que no tienen se reportan aparte.
    unassigned_active = unassigned_active_lines(invoice)
    return {
        "with_fee": unassigned_active.filter(fee__isnull=False).count(),
        "without_fee": unassigned_active.filter(fee__isnull=True).count(),
    }


def invoice_summary(invoice):
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
    unassigned = unassigned_counts(invoice)
    return {
        "assign_blocked_reason": assign_blocked_reason(invoice),
        "other_open_invoice": Invoice.objects.filter(status=Invoice.Status.OPEN).exclude(pk=invoice.pk).first(),
        "lines_count": lines_count,
        "paid_count": paid_count,
        "carried_count": carried_count,
        "pending_count": lines_count - paid_count - carried_count,
        "paid_percent": round(paid_count * 100 / lines_count) if lines_count else 0,
        "expected_amount": counts["expected_amount"] or 0,
        "collected_amount": counts["collected_amount"] or 0,
        "unassigned_active_count": unassigned["with_fee"],
        "unassigned_without_fee_count": unassigned["without_fee"],
    }


# ===== Recibos (líneas de factura) =====

def search_invoice_lines(invoice, query="", status=""):
    invoice_lines = (
        InvoiceLine.objects.filter(invoice=invoice)
        .select_related("line", "line__customer", "line__location", "fee", "late_fee", "carried_to")
        .order_by("line__code")
    )
    if query:
        invoice_lines = invoice_lines.filter(
            Q(code__icontains=query)
            | Q(line__code__icontains=query)
            | Q(line__location__name__icontains=query)
            | Q(line__customer__firstName__icontains=query)
            | Q(line__customer__lastName__icontains=query)
        )
    if status == "paid":
        invoice_lines = invoice_lines.filter(isPaid=True)
    elif status == "pending":
        # En una factura cerrada estos son los vencidos.
        invoice_lines = invoice_lines.filter(isPaid=False, carried_to__isnull=True)
    elif status == "carried":
        invoice_lines = invoice_lines.filter(carried_to__isnull=False)
    return invoice_lines


def _create_invoice_line(invoice, line, user):
    # InvoiceLine.save() re-saves itself to generate `code`, so it must be
    # created via a plain save() rather than objects.create() (which forces
    # an INSERT on both saves and raises a duplicate-pk IntegrityError).
    InvoiceLine(invoice=invoice, line=line, created_by=user).save()


def ensure_can_assign(invoice):
    blocked_reason = assign_blocked_reason(invoice)
    if blocked_reason:
        raise ValidationError(blocked_reason)


def assign_all_lines(invoice, user):
    """Asigna a la factura todas las líneas activas con cuota que aún no tiene.

    Devuelve (asignadas, sin_cuota) para que la vista informe ambas cifras.
    """
    ensure_can_assign(invoice)
    unassigned_active = unassigned_active_lines(invoice)
    without_fee_count = unassigned_active.filter(fee__isnull=True).count()
    created_count = 0
    for line in unassigned_active.filter(fee__isnull=False).select_related("fee"):
        _create_invoice_line(invoice, line, user)
        created_count += 1
    return created_count, without_fee_count


def assign_line(invoice, line, user):
    ensure_can_assign(invoice)
    _create_invoice_line(invoice, line, user)


def toggle_invoice_line_paid(invoice_line):
    if invoice_line.invoice.is_draft:
        raise ValidationError("La factura sigue en borrador; ábrela para poder registrar pagos.")
    if invoice_line.invoice.is_closed:
        raise ValidationError("La factura está cerrada; sus recibos ya no se pueden modificar.")
    if invoice_line.is_carried:
        raise ValidationError(
            f"El saldo de este recibo se trasladó al recibo {invoice_line.carried_to.code}; cóbralo en ese recibo."
        )
    invoice_line.isPaid = not invoice_line.isPaid
    invoice_line.save(update_fields=["isPaid"])
    return invoice_line


def ensure_late_fee_editable(invoice_line):
    # Un recibo pagado o ya trasladado está cerrado: cambiar su mora descuadraría lo cobrado.
    if invoice_line.isPaid or invoice_line.is_carried or invoice_line.invoice.is_closed:
        raise ValidationError("Solo se puede cambiar la mora de un recibo pendiente.")


def change_late_fee(invoice_line, late_fee):
    ensure_late_fee_editable(invoice_line)
    invoice_line.set_late_fee(late_fee)
    invoice_line.save(update_fields=["late_fee", "late_fee_amount"])
    return invoice_line


def remove_invoice_line(invoice_line):
    if invoice_line.invoice.is_closed:
        raise ValidationError("No se pueden quitar líneas de una factura cerrada.")
    if invoice_line.isPaid:
        raise ValidationError("No se puede quitar una línea que ya está pagada.")
    if invoice_line.is_carried:
        raise ValidationError("No se puede quitar un recibo cuyo saldo ya se trasladó a un recibo posterior.")
    invoice_line.delete()


# ===== Impresión de recibos =====

def printable_receipts(invoice):
    # Los recibos trasladados no se imprimen: su saldo ya va en el recibo posterior.
    return (
        InvoiceLine.objects.filter(invoice=invoice, carried_to__isnull=True)
        .select_related("line", "line__customer", "line__location")
        .order_by("line__code")
    )


def receipts_for_selection(invoice, ids=None):
    invoice_lines = InvoiceLine.objects.filter(invoice=invoice)
    if ids is not None:
        invoice_lines = invoice_lines.filter(pk__in=ids)
    return invoice_lines.select_related("line", "line__customer", "line__location", "carried_to").order_by(
        "line__code"
    )


def receipts_pdf(invoice, invoice_lines, template_name):
    """Genera el PDF de los recibos. Devuelve los bytes o None si xhtml2pdf falla."""
    html = render_to_string(template_name, {"invoice": invoice, "invoice_lines": invoice_lines})
    buffer = io.BytesIO()
    if pisa.CreatePDF(html, dest=buffer).err:
        return None
    return buffer.getvalue()


def receipts_by_status(invoice, query="", status=""):
    """Recibos de la factura agrupados por estado para el listado en PDF.

    Respeta los mismos filtros (búsqueda y estado) que la tabla de la factura.
    """
    pending_label = "Vencidos" if invoice.is_closed else "Pendientes"
    groups = {
        "pending": {"label": pending_label, "receipts": [], "total": 0},
        "paid": {"label": "Pagados", "receipts": [], "total": 0},
        "carried": {"label": "Trasladados", "receipts": [], "total": 0},
    }
    for receipt in search_invoice_lines(invoice, query, status):
        if receipt.isPaid:
            key = "paid"
        elif receipt.is_carried:
            key = "carried"
        else:
            key = "pending"
        groups[key]["receipts"].append(receipt)
        groups[key]["total"] += receipt.total

    filters = []
    if query:
        filters.append(f"Búsqueda: {query}")
    if status in groups:
        filters.append(f"Estado: {groups[status]['label']}")
        groups = {status: groups[status]}
    return {
        "invoice": invoice,
        "groups": list(groups.values()),
        "filters": filters,
        "receipts_count": sum(len(group["receipts"]) for group in groups.values()),
    }
