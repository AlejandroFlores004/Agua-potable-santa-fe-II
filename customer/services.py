from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

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
