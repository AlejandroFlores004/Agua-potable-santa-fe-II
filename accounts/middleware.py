from django.contrib import messages
from django.shortcuts import render

from shell.htmx import messages_response

from .permissions import MODULE_NAMES, PROTECTED_APPS, can_read, can_write

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


class ModulePermissionMiddleware:
    """Controla el acceso a cada módulo según los permisos de los grupos del usuario.

    Consultar (GET) requiere cualquier permiso del módulo; modificar (POST) requiere
    un permiso de crear, editar o eliminar. Así las vistas de cada app no necesitan
    revisar permisos por su cuenta.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        app_label = view_func.__module__.split(".")[0]
        # Sin sesión, el login_required de la vista se encarga de redirigir al login.
        if app_label not in PROTECTED_APPS or not request.user.is_authenticated:
            return None

        if request.method in SAFE_METHODS:
            allowed = can_read(request.user, app_label)
            action = "consultar"
        else:
            allowed = can_write(request.user, app_label)
            action = "modificar"
        if allowed:
            return None

        module = MODULE_NAMES[app_label]
        if getattr(request, "htmx", False):
            messages.error(request, f"No tienes permiso para {action} {module}.")
            response = messages_response(request)
            response["HX-Reswap"] = "none"
            return response
        return render(request, "403.html", {"module": module, "action": action}, status=403)
