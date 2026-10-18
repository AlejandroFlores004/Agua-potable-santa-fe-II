from django.core.paginator import Paginator

PAGE_SIZE = 20


def paginate(request, queryset, per_page=PAGE_SIZE):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))
