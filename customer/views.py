from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from shell.htmx import messages_response
from shell.pagination import paginate

from . import services
from .forms import CustomerForm, get_line_formset_class
from .models import Customer


@login_required(login_url="login")
def customer_home(request):
    query = request.GET.get("q", "").strip()
    page_obj = paginate(request, services.search_customers(query))
    context = {"customers": page_obj.object_list, "page_obj": page_obj, "query": query}
    if request.htmx:
        return render(request, "partials/customer/_customer_table.html", context)
    return render(request, "customer_home.html", context)


@login_required(login_url="login")
def customer_detail(request, pk):
    customer = get_object_or_404(Customer.objects.select_related("created_by"), pk=pk)
    return render(request, "customer_detail.html", services.customer_history(customer))


@login_required(login_url="login")
def customer_form(request, pk=None):
    customer = get_object_or_404(Customer, pk=pk) if pk else Customer()
    is_new = customer.pk is None
    LineFormSet = get_line_formset_class(extra=1 if is_new else 0)

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        formset = LineFormSet(request.POST, instance=customer, prefix="lines")

        if form.is_valid() and formset.is_valid():
            services.save_customer(form, formset, request.user)
            messages.success(
                request,
                "Cliente creado correctamente." if is_new else "Cliente actualizado correctamente.",
            )
            if form.dui_warning:
                messages.warning(request, form.dui_warning)
            return messages_response(request, "customerSaved")
    else:
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
    try:
        services.delete_customer(customer)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, "Cliente eliminado correctamente.")
    return messages_response(request, "customerSaved")
