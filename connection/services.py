from django.db.models import Q

from .models import Line


def search_lines(query=""):
    lines = (
        Line.objects.select_related("customer", "location", "fee", "created_by")
        .order_by("-created_at")
    )
    if query:
        lines = lines.filter(
            Q(code__icontains=query)
            | Q(description__icontains=query)
            | Q(location__name__icontains=query)
            | Q(customer__firstName__icontains=query)
            | Q(customer__lastName__icontains=query)
        )
    return lines


def save_line(line, user):
    if line.pk is None:
        line.created_by = user
    line.save()
    return line


def toggle_line(line):
    # Las mechas no se eliminan (las usan los recibos); solo se activan o desactivan.
    line.isActive = not line.isActive
    line.save(update_fields=["isActive", "updated_at"])
    return line
