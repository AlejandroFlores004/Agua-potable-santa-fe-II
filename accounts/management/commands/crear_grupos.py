from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from accounts.permissions import Level, set_group_level

# Grupo -> nivel por módulo. Los módulos que no aparecen quedan sin acceso.
DEFAULT_GROUPS = {
    "Administración": {
        "customer": Level.FULL,
        "connection": Level.FULL,
        "billing": Level.FULL,
        "expense": Level.FULL,
        "auth": Level.FULL,
    },
    "Cobranza": {
        "customer": Level.READ,
        "connection": Level.READ,
        "billing": Level.FULL,
    },
    "Consulta": {
        "customer": Level.READ,
        "connection": Level.READ,
        "billing": Level.READ,
        "expense": Level.READ,
    },
}


class Command(BaseCommand):
    help = "Crea los grupos base (Administración, Cobranza, Consulta). No modifica los que ya existen."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Vuelve a aplicar los permisos base también a los grupos que ya existen.",
        )

    def handle(self, *args, reset=False, **options):
        for name, levels in DEFAULT_GROUPS.items():
            group, created = Group.objects.get_or_create(name=name)
            if not created and not reset:
                self.stdout.write(f"· «{name}» ya existe, se deja como está.")
                continue
            group.permissions.clear()
            for app_label, level in levels.items():
                set_group_level(group, app_label, level)
            self.stdout.write(self.style.SUCCESS(f"✓ «{name}» {'creado' if created else 'restablecido'}."))
