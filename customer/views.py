from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .forms import CustomerForm, get_line_formset_class
from .models import Customer


def _get_customers(request):
    customers = (
        Customer.objects.select_related("created_by")
        .prefetch_related("lines__location")
        .order_by("-created_at")
    )
    query = request.GET.get("q", "").strip()
    if query:
        customers = customers.filter(
            Q(firstName__icontains=query)
            | Q(lastName__icontains=query)
            | Q(dui__icontains=query)
            | Q(email__icontains=query)
            | Q(number__icontains=query)
        )
    return customers, query


@login_required(login_url="login")
def customer_home(request):
    customers, query = _get_customers(request)
    context = {"customers": customers, "query": query}
    if request.htmx:
        return render(request, "partials/customer/_customer_table.html", context)
    return render(request, "customer_home.html", context)


@login_required(login_url="login")
def customer_form(request, pk=None):
    customer = get_object_or_404(Customer, pk=pk) if pk else Customer()
    is_new = customer.pk is None
    LineFormSet = get_line_formset_class(extra=1 if is_new else 0)

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        formset = LineFormSet(request.POST, instance=customer, prefix="lines")

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                customer = form.save(commit=False)
                if is_new:
                    customer.created_by = request.user
                customer.save()

                lines = formset.save(commit=False)
                for line in lines:
                    if not line.pk:
                        line.created_by = request.user
                    line.save()
                for line in formset.deleted_objects:
                    line.delete()

            messages.success(
                request,
                "Cliente creado correctamente." if is_new else "Cliente actualizado correctamente.",
            )
            response = render(request, "partials/customer/_form_success_oob.html")
            response["HX-Trigger"] = "customerSaved"
            return response

        return render(
            request,
            "partials/customer/_customer_form_modal.html",
            {"form": form, "formset": formset, "customer": customer, "is_new": is_new},
        )

    form = CustomerForm(instance=customer)
    formset = LineFormSet(instance=customer, prefix="lines")
    return render(
        request,
        "partials/customer/_customer_form_modal.html",
        {"form": form, "formset": formset, "customer": customer, "is_new": is_new},
    )


@login_required(login_url="login")
@require_POST
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer.delete()
    messages.success(request, "Cliente eliminado correctamente.")
    response = render(request, "partials/customer/_form_success_oob.html")
    response["HX-Trigger"] = "customerSaved"
    return response
