from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from shell.htmx import messages_response
from shell.pagination import paginate

from .forms import LineForm
from .models import Line


def _get_lines(request):
    lines = (
        Line.objects.select_related("customer", "location", "fee", "created_by")
        .order_by("-created_at")
    )
    query = request.GET.get("q", "").strip()
    if query:
        lines = lines.filter(
            Q(code__icontains=query)
            | Q(description__icontains=query)
            | Q(location__name__icontains=query)
            | Q(customer__firstName__icontains=query)
            | Q(customer__lastName__icontains=query)
        )
    return lines, query


@login_required(login_url="login")
def line_home(request):
    lines, query = _get_lines(request)
    page_obj = paginate(request, lines)
    context = {"lines": page_obj.object_list, "page_obj": page_obj, "query": query}
    if request.htmx:
        return render(request, "partials/line/_line_table.html", context)
    return render(request, "mechas_home.html", context)


@login_required(login_url="login")
def line_form(request, pk=None):
    line = get_object_or_404(Line, pk=pk) if pk else Line()
    is_new = line.pk is None

    if request.method == "POST":
        form = LineForm(request.POST, instance=line)

        if form.is_valid():
            line = form.save(commit=False)
            if is_new:
                line.created_by = request.user
            line.save()

            messages.success(
                request,
                "Mecha creada correctamente." if is_new else "Mecha actualizada correctamente.",
            )
            return messages_response(request, "lineSaved")

        return render(
            request,
            "partials/line/_line_form_modal.html",
            {"form": form, "line": line, "is_new": is_new},
        )

    form = LineForm(instance=line)
    return render(
        request,
        "partials/line/_line_form_modal.html",
        {"form": form, "line": line, "is_new": is_new},
    )


@login_required(login_url="login")
@require_POST
def line_toggle(request, pk):
    # Las mechas no se eliminan (las usan los recibos); solo se activan o desactivan.
    line = get_object_or_404(Line, pk=pk)
    line.isActive = not line.isActive
    line.save(update_fields=["isActive", "updated_at"])
    messages.success(request, "Mecha activada correctamente." if line.isActive else "Mecha desactivada correctamente.")
    return messages_response(request, "lineSaved")
