from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal

from django.db.models import Prefetch, Q

from billing.models import InvoiceLine

from .models import Customer


def search_customers(query=""):
    customers = (
        Customer.objects.select_related("created_by")
        .prefetch_related("lines__location")
        .order_by("-created_at")
    )
    if query:
        customers = customers.filter(
            Q(firstName__icontains=query)
            | Q(lastName__icontains=query)
            | Q(dui__icontains=query)
            | Q(email__icontains=query)
            | Q(number__icontains=query)
        )
    return customers


def customer_history(customer):
    """Mechas del cliente con todos sus recibos, del más reciente al más antiguo."""
    receipts = InvoiceLine.objects.select_related("invoice", "fee", "late_fee", "carried_to").order_by(
        "-invoice__start_date", "-created_at"
    )
    lines = list(
        customer.lines.select_related("location", "fee")
        .prefetch_related(Prefetch("invoiceline_set", queryset=receipts, to_attr="receipts"))
        .order_by("-isActive", "code")
    )

    # Un recibo trasladado ya está sumado en el saldo anterior del que lo absorbió,
    # así que la deuda real son los impagos sin trasladar.
    all_receipts = [receipt for line in lines for receipt in line.receipts]
    pending = [r for r in all_receipts if not r.isPaid and not r.is_carried]
    return {
        "customer": customer,
        "lines": lines,
        "receipts_count": len(all_receipts),
        "pending_total": sum((r.total for r in pending), Decimal("0")),
        "overdue_total": sum((r.total for r in pending if r.invoice.is_closed), Decimal("0")),
        "paid_total": sum((r.total for r in all_receipts if r.isPaid), Decimal("0")),
    }


def save_customer(form, line_formset, user):
    """Guarda el cliente y sus mechas juntos; si algo falla no queda nada a medias.

    Recibe el formulario y el formset ya validados porque el formset necesita
    el cliente guardado para poder enlazarle las mechas nuevas.
    """
    with transaction.atomic():
        customer = form.save(commit=False)
        if customer.pk is None:
            customer.created_by = user
        customer.save()

        for line in line_formset.save(commit=False):
            if not line.pk:
                line.created_by = user
            line.save()
    return customer


def delete_customer(customer):
    # Las mechas no se eliminan, así que un cliente con mechas tampoco.
    if customer.lines.exists():
        raise ValidationError("No se puede eliminar un cliente con mechas. Desactiva sus mechas en su lugar.")
    customer.delete()
