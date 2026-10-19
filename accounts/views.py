from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from shell.htmx import messages_response
from shell.pagination import paginate

from . import services
from .forms import AdminSetPasswordForm, GroupForm, ProfileForm, ProfilePasswordForm, UserForm
from .permissions import MODULES


def in_spanish(view):
    # Los mensajes de validación de Django (contraseñas, login) salen en el idioma activo.
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        with translation.override("es"):
            return view(request, *args, **kwargs)
    return wrapper


def _safe_next(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return next_url
    return ""


# ===== Sesión =====

@in_spanish
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request) or settings.LOGIN_REDIRECT_URL)

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        # Sin "Recordarme" la sesión termina al cerrar el navegador.
        if not request.POST.get("remember"):
            request.session.set_expiry(0)
        return redirect(_safe_next(request) or settings.LOGIN_REDIRECT_URL)

    return render(request, "registration/login.html", {"form": form, "next": _safe_next(request)})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "Cerraste sesión correctamente.")
    return redirect("login")


# ===== Mi cuenta =====

@login_required
@in_spanish
def profile_view(request):
    profile_form = ProfileForm(instance=request.user)
    password_form = ProfilePasswordForm(request.user)

    if request.method == "POST" and request.POST.get("action") == "profile":
        profile_form = ProfileForm(request.POST, instance=request.user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Tus datos se actualizaron correctamente.")
            return redirect("profile")
    elif request.method == "POST" and request.POST.get("action") == "password":
        password_form = ProfilePasswordForm(request.user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            # Sin esto, cambiar la contraseña cerraría la sesión actual.
            update_session_auth_hash(request, user)
            messages.success(request, "Tu contraseña se cambió correctamente.")
            return redirect("profile")

    return render(request, "profile.html", {
        "profile_form": profile_form,
        "password_form": password_form,
        "groups": request.user.groups.order_by("name"),
    })


# ===== Usuarios =====

@login_required
@permission_required("auth.view_user", raise_exception=True)
def user_home(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "active")
    group = request.GET.get("group", "")
    page_obj = paginate(request, services.search_users(query, status, group))
    context = {
        "users": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "group": group,
        "groups": Group.objects.order_by("name"),
        "counts": services.user_counts(),
    }
    if request.htmx:
        return render(request, "partials/accounts/_users_table.html", context)
    return render(request, "users_home.html", context)


@login_required
@in_spanish
def user_form(request, pk=None):
    user = get_object_or_404(User, pk=pk) if pk else User()
    is_new = user.pk is None
    if not request.user.has_perm("auth.add_user" if is_new else "auth.change_user"):
        raise PermissionDenied
    services.check_can_manage(request.user, user)

    if request.method == "POST":
        form = UserForm(request.POST, instance=user, editor=request.user)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Usuario «{user.username}» creado correctamente." if is_new else f"Usuario «{user.username}» actualizado correctamente.",
            )
            return messages_response(request, "userSaved")
    else:
        form = UserForm(instance=user, editor=request.user)

    return render(request, "partials/accounts/_user_form_modal.html", {"form": form, "account": user, "is_new": is_new})


@login_required
@permission_required("auth.change_user", raise_exception=True)
@in_spanish
def user_password(request, pk):
    user = get_object_or_404(User, pk=pk)
    services.check_can_manage(request.user, user)

    if request.method == "POST":
        form = AdminSetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            if user == request.user:
                update_session_auth_hash(request, user)
            messages.success(request, f"Contraseña de «{user.username}» cambiada correctamente.")
            return messages_response(request, "userSaved")
    else:
        form = AdminSetPasswordForm(user)

    return render(request, "partials/accounts/_user_password_modal.html", {"form": form, "account": user})


@login_required
@permission_required("auth.change_user", raise_exception=True)
@require_POST
def user_toggle(request, pk):
    user = get_object_or_404(User, pk=pk)
    try:
        services.toggle_user(user, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(
            request,
            f"Usuario «{user.username}» activado correctamente." if user.is_active
            else f"Usuario «{user.username}» desactivado. Ya no podrá iniciar sesión.",
        )
    return messages_response(request, "userSaved")


# ===== Grupos =====

@login_required
@permission_required("auth.view_group", raise_exception=True)
def group_home(request):
    context = {"groups": services.groups_with_levels(), "modules": MODULES}
    if request.htmx:
        return render(request, "partials/accounts/_groups_table.html", context)
    return render(request, "groups_home.html", context)


@login_required
def group_form(request, pk=None):
    group = get_object_or_404(Group, pk=pk) if pk else Group()
    is_new = group.pk is None
    if not request.user.has_perm("auth.add_group" if is_new else "auth.change_group"):
        raise PermissionDenied

    if request.method == "POST":
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            group = form.save()
            messages.success(
                request,
                f"Grupo «{group.name}» creado correctamente." if is_new else f"Grupo «{group.name}» actualizado correctamente.",
            )
            return messages_response(request, "groupSaved")
    else:
        form = GroupForm(instance=group)

    return render(request, "partials/accounts/_group_form_modal.html", {"form": form, "group": group, "is_new": is_new})


@login_required
@permission_required("auth.delete_group", raise_exception=True)
@require_POST
def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    group.delete()
    messages.success(request, f"Grupo «{group.name}» eliminado. Sus usuarios perdieron los permisos que les daba.")
    return messages_response(request, "groupSaved")
