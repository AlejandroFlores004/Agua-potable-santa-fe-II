from django.contrib.auth.models import Permission
from django.db import models

# Módulos que se controlan por grupo: (app de Django dueña de los permisos, nombre visible).
MODULES = [
    ("customer", "Clientes"),
    ("connection", "Mechas"),
    ("billing", "Recibos y cuotas"),
    ("expense", "Gastos"),
    ("auth", "Usuarios y grupos"),
]
MODULE_NAMES = dict(MODULES)

# Apps cuyas vistas protege ModulePermissionMiddleware. Las de "auth" (este módulo)
# se protegen con decoradores en accounts.views.
PROTECTED_APPS = {"customer", "connection", "billing", "expense"}

WRITE_ACTIONS = ("add_", "change_", "delete_")


class Level(models.TextChoices):
    NONE = "none", "Sin acceso"
    READ = "read", "Solo consulta"
    FULL = "full", "Acceso completo"
    # Combinación que no coincide con un nivel, p. ej. asignada desde el admin de Django.
    CUSTOM = "custom", "Personalizado"


def module_permissions(app_label):
    permissions = Permission.objects.filter(content_type__app_label=app_label)
    if app_label == "auth":
        # Los permisos sobre el modelo Permission no se gestionan desde aquí.
        permissions = permissions.filter(content_type__model__in=["user", "group"])
    return permissions


def permissions_for_level(app_label, level):
    if level == Level.FULL:
        return module_permissions(app_label)
    if level == Level.READ:
        return module_permissions(app_label).filter(codename__startswith="view_")
    return Permission.objects.none()


def level_for(group_permission_ids, app_label):
    module_ids = dict(module_permissions(app_label).values_list("pk", "codename"))
    granted = set(module_ids) & set(group_permission_ids)
    view_ids = {pk for pk, codename in module_ids.items() if codename.startswith("view_")}
    if not granted:
        return Level.NONE
    if granted == set(module_ids):
        return Level.FULL
    if granted == view_ids:
        return Level.READ
    return Level.CUSTOM


def set_group_level(group, app_label, level):
    if level == Level.CUSTOM:
        return
    group.permissions.remove(*module_permissions(app_label))
    group.permissions.add(*permissions_for_level(app_label, level))


def can_read(user, app_label):
    return user.has_module_perms(app_label)


def can_write(user, app_label):
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    prefix = f"{app_label}."
    return any(
        perm.startswith(prefix) and perm[len(prefix):].startswith(WRITE_ACTIONS)
        for perm in user.get_all_permissions()
    )
