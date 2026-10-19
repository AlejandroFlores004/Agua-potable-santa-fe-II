from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import MODULE_NAMES, can_read
from customer.models import Customer

from . import services


def module_required(*app_labels):
    """Los reportes muestran datos de otros módulos: exige poder consultarlos todos.

    ModulePermissionMiddleware solo protege las vistas de cada módulo, no las de esta app.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            for app_label in app_labels:
                if not can_read(request.user, app_label):
                    context = {"module": MODULE_NAMES[app_label], "action": "consultar"}
                    return render(request, "403.html", context, status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _pdf_response(request, template_name, context, filename):
    pdf = services.render_pdf(template_name, context)
    if pdf is None:
        messages.error(request, "Ocurrió un error al generar el reporte en PDF.")
        return redirect("reports_home")
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


def _today():
    return f"{timezone.localdate():%d-%m-%Y}"


@login_required(login_url="login")
def reports_home(request):
    user = request.user
    context = {
        "can_customers": can_read(user, "customer"),
        "can_lines": can_read(user, "connection"),
        "can_billing": can_read(user, "billing"),
        **services.report_form_options(),
    }
    return render(request, "reports_home.html", context)


@login_required(login_url="login")
@module_required("customer")
def customers_pdf(request):
    return _pdf_response(
        request, "reports/pdf/customers.html", services.customers_report(), f"clientes_{_today()}.pdf"
    )


@login_required(login_url="login")
@module_required("customer")
def customer_observations_pdf(request):
    return _pdf_response(
        request,
        "reports/pdf/customer_observations.html",
        services.customer_observations_report(),
        f"clientes_con_observaciones_{_today()}.pdf",
    )


@login_required(login_url="login")
@module_required("customer", "billing")
def customer_statement_pdf(request):
    # Llega desde el formulario del reporte (?customer=<pk>).
    customer_id = request.GET.get("customer", "")
    if not customer_id.isdigit():
        messages.error(request, "Selecciona un cliente para generar su estado de cuenta.")
        return redirect("reports_home")
    customer = get_object_or_404(Customer, pk=customer_id)
    filename = f"estado_de_cuenta_{customer.firstName}_{customer.lastName}_{_today()}.pdf".replace(" ", "_")
    return _pdf_response(
        request, "reports/pdf/customer_statement.html", services.customer_statement(customer), filename
    )


@login_required(login_url="login")
@module_required("connection")
def lines_pdf(request):
    context = services.lines_report(
        status=request.GET.get("status", "active"),
        location_id=request.GET.get("location", ""),
        fee_id=request.GET.get("fee", ""),
    )
    return _pdf_response(request, "reports/pdf/lines.html", context, f"mechas_{_today()}.pdf")


@login_required(login_url="login")
@module_required("billing")
def debtors_pdf(request):
    context = services.debtors_report(only_overdue=request.GET.get("overdue") == "1")
    return _pdf_response(request, "reports/pdf/debtors.html", context, f"morosos_{_today()}.pdf")
