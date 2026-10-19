from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q

from .permissions import MODULES, level_for


# ===== Usuarios =====

def check_can_manage(editor, user):
    # Solo un administrador total puede modificar a otro administrador total;
    # si no, cualquiera con permiso de usuarios podría tomar su cuenta.
    if user.is_superuser and not editor.is_superuser:
        raise PermissionDenied


def search_users(query="", status="active", group=""):
    users = User.objects.prefetch_related("groups").order_by("-is_active", "username")
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)
    if group == "none":
        users = users.filter(groups__isnull=True, is_superuser=False)
    elif group.isdigit():
        users = users.filter(groups__pk=group)
    return users


def user_counts():
    # distinct: el filtro por grupos une la tabla de grupos y repetiría usuarios.
    return User.objects.aggregate(
        total=Count("id", distinct=True),
        active=Count("id", distinct=True, filter=Q(is_active=True)),
        inactive=Count("id", distinct=True, filter=Q(is_active=False)),
        admins=Count("id", distinct=True, filter=Q(is_active=True, is_superuser=True)),
        without_group=Count("id", distinct=True, filter=Q(is_active=True, is_superuser=False, groups__isnull=True)),
    )


def toggle_user(user, editor):
    check_can_manage(editor, user)
    if user == editor:
        raise ValidationError("No puedes desactivar tu propia cuenta.")
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    return user


# ===== Grupos =====

def groups_with_levels():
    """Grupos con `levels`: el nivel de acceso que da cada grupo en cada módulo."""
    groups = list(
        Group.objects.prefetch_related("permissions")
        .annotate(users_count=Count("user", filter=Q(user__is_active=True)))
        .order_by("name")
    )
    for group in groups:
        permission_ids = {permission.pk for permission in group.permissions.all()}
        group.levels = [(label, level_for(permission_ids, app_label)) for app_label, label in MODULES]
    return groups
