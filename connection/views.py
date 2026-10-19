from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from shell.htmx import messages_response
from shell.pagination import paginate

from . import services
from .forms import LineForm
from .models import Line


@login_required(login_url="login")
def line_home(request):
    query = request.GET.get("q", "").strip()
    page_obj = paginate(request, services.search_lines(query))
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
            services.save_line(form.save(commit=False), request.user)
            messages.success(
                request,
                "Mecha creada correctamente." if is_new else "Mecha actualizada correctamente.",
            )
            return messages_response(request, "lineSaved")
    else:
        form = LineForm(instance=line)

    return render(
        request,
        "partials/line/_line_form_modal.html",
        {"form": form, "line": line, "is_new": is_new},
    )


@login_required(login_url="login")
@require_POST
def line_toggle(request, pk):
    line = services.toggle_line(get_object_or_404(Line, pk=pk))
    messages.success(request, "Mecha activada correctamente." if line.isActive else "Mecha desactivada correctamente.")
    return messages_response(request, "lineSaved")
