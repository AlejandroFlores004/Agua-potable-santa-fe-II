from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .forms import GroupForm
from .permissions import Level, level_for, set_group_level

PASSWORD = "Agua-Potable-2026"


def make_group(name, **levels):
    group = Group.objects.create(name=name)
    for app_label, level in levels.items():
        set_group_level(group, app_label, level)
    return group


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("cobrador", password=PASSWORD)

    def test_login_redirects_home(self):
        response = self.client.post(reverse("login"), {"username": "cobrador", "password": PASSWORD})
        self.assertRedirects(response, reverse("home"))

    def test_login_follows_safe_next_only(self):
        response = self.client.post(
            reverse("login"), {"username": "cobrador", "password": PASSWORD, "next": "/expense/"}
        )
        self.assertRedirects(response, "/expense/", fetch_redirect_response=False)
        self.client.logout()
        response = self.client.post(
            reverse("login"), {"username": "cobrador", "password": PASSWORD, "next": "https://malo.com/"}
        )
        self.assertRedirects(response, reverse("home"))

    def test_wrong_password_shows_error(self):
        response = self.client.post(reverse("login"), {"username": "cobrador", "password": "otra"})
        self.assertContains(response, "Usuario o contraseña incorrectos")

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(reverse("login"), {"username": "cobrador", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_session_ends_with_browser_unless_remember(self):
        self.client.post(reverse("login"), {"username": "cobrador", "password": PASSWORD})
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.client.logout()
        self.client.post(reverse("login"), {"username": "cobrador", "password": PASSWORD, "remember": "1"})
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))


class LevelTests(TestCase):
    def test_levels_round_trip(self):
        group = make_group("G", customer=Level.FULL, billing=Level.READ)
        ids = set(group.permissions.values_list("pk", flat=True))
        self.assertEqual(level_for(ids, "customer"), Level.FULL)
        self.assertEqual(level_for(ids, "billing"), Level.READ)
        self.assertEqual(level_for(ids, "expense"), Level.NONE)

    def test_partial_permissions_are_custom_and_kept(self):
        group = make_group("G")
        group.permissions.add(*Group.permissions.field.related_model.objects.filter(codename="add_customer"))
        form = GroupForm(
            {"name": "G", "level_customer": "custom", "level_connection": "read",
             "level_billing": "none", "level_expense": "none", "level_auth": "none"},
            instance=group,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertTrue(group.permissions.filter(codename="add_customer").exists())
        self.assertTrue(group.permissions.filter(codename="view_line").exists())


class ModulePermissionMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("consulta", password=PASSWORD)
        self.client.force_login(self.user)

    def test_user_without_group_is_denied(self):
        response = self.client.get(reverse("expense_home"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Gastos", status_code=403)

    def test_read_level_can_view_but_not_modify(self):
        self.user.groups.add(make_group("Consulta", expense=Level.READ))
        self.assertEqual(self.client.get(reverse("expense_home")).status_code, 200)
        response = self.client.post(reverse("expense_create"), {"concept": "x"}, HTTP_HX_REQUEST="true")
        self.assertEqual(response["HX-Reswap"], "none")
        self.assertContains(response, "No tienes permiso para modificar Gastos")

    def test_full_level_can_modify(self):
        self.user.groups.add(make_group("Todo", expense=Level.FULL))
        response = self.client.post(
            reverse("expense_create"),
            {"concept": "Cloro", "amount": "10", "date": "2026-10-01"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response["HX-Trigger"], "expenseSaved")

    def test_anonymous_still_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("expense_home"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('expense_home')}")

    def test_navbar_hides_modules_without_access(self):
        self.user.groups.add(make_group("Gastos", expense=Level.READ))
        response = self.client.get(reverse("home"))
        # Etiquetas del dock móvil; el dashboard también enlaza a los módulos.
        self.assertContains(response, "<span>Gastos</span>")
        self.assertNotContains(response, "<span>Clientes</span>")
        self.assertNotContains(response, "<span>Recibos</span>")


class UserManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("jefe", password=PASSWORD)
        self.admin.groups.add(make_group("Administración", auth=Level.FULL))
        self.client.force_login(self.admin)
        self.cobranza = make_group("Cobranza", billing=Level.FULL)

    def test_requires_permission(self):
        self.client.force_login(User.objects.create_user("otro", password=PASSWORD))
        self.assertEqual(self.client.get(reverse("user_home")).status_code, 403)
        self.assertEqual(self.client.get(reverse("group_home")).status_code, 403)

    def test_create_user_with_groups(self):
        response = self.client.post(reverse("user_create"), {
            "username": "ana", "first_name": "Ana", "groups": [self.cobranza.pk],
            "is_active": "on", "password1": PASSWORD, "password2": PASSWORD,
        })
        self.assertEqual(response["HX-Trigger"], "userSaved")
        ana = User.objects.get(username="ana")
        self.assertTrue(ana.check_password(PASSWORD))
        self.assertEqual(list(ana.groups.all()), [self.cobranza])
        self.assertFalse(ana.is_superuser)

    def test_weak_password_is_rejected_in_spanish(self):
        response = self.client.post(reverse("user_create"), {
            "username": "ana", "is_active": "on", "password1": "123", "password2": "123",
        })
        self.assertFalse(User.objects.filter(username="ana").exists())
        self.assertContains(response, "contraseña")

    def test_non_superuser_cannot_touch_superusers(self):
        root = User.objects.create_superuser("root", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("user_edit", args=[root.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("user_toggle", args=[root.pk])).status_code, 403)
        response = self.client.post(
            reverse("user_password", args=[root.pk]), {"new_password1": "x", "new_password2": "x"}
        )
        self.assertEqual(response.status_code, 403)
        root.refresh_from_db()
        self.assertTrue(root.is_active)

    def test_non_superuser_cannot_grant_superuser(self):
        self.client.post(reverse("user_create"), {
            "username": "ana", "is_active": "on", "is_superuser": "on",
            "password1": PASSWORD, "password2": PASSWORD,
        })
        self.assertFalse(User.objects.get(username="ana").is_superuser)

    def test_cannot_deactivate_self(self):
        self.client.post(reverse("user_toggle", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        # Tampoco desde el formulario de edición.
        self.client.post(reverse("user_edit", args=[self.admin.pk]), {"username": "jefe"})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_toggle_and_reset_password(self):
        ana = User.objects.create_user("ana", password=PASSWORD)
        self.client.post(reverse("user_toggle", args=[ana.pk]))
        ana.refresh_from_db()
        self.assertFalse(ana.is_active)
        self.client.post(
            reverse("user_password", args=[ana.pk]),
            {"new_password1": "Nueva-Clave-2026", "new_password2": "Nueva-Clave-2026"},
        )
        ana.refresh_from_db()
        self.assertTrue(ana.check_password("Nueva-Clave-2026"))

    def test_user_list_filters(self):
        User.objects.create_user("ana").groups.add(self.cobranza)
        User.objects.create_user("beto", is_active=False)
        response = self.client.get(reverse("user_home"), {"group": self.cobranza.pk})
        self.assertEqual([u.username for u in response.context["users"]], ["ana"])
        response = self.client.get(reverse("user_home"), {"status": "inactive"})
        self.assertEqual([u.username for u in response.context["users"]], ["beto"])


class GroupManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("root", password=PASSWORD)
        self.client.force_login(self.admin)

    def test_create_group_with_levels(self):
        response = self.client.post(reverse("group_create"), {
            "name": "Cobranza", "level_customer": "read", "level_connection": "none",
            "level_billing": "full", "level_expense": "none", "level_auth": "none",
        })
        self.assertEqual(response["HX-Trigger"], "groupSaved")
        group = Group.objects.get(name="Cobranza")
        ids = set(group.permissions.values_list("pk", flat=True))
        self.assertEqual(level_for(ids, "customer"), Level.READ)
        self.assertEqual(level_for(ids, "billing"), Level.FULL)
        self.assertEqual(level_for(ids, "connection"), Level.NONE)

    def test_delete_group(self):
        group = make_group("Temporal")
        self.client.post(reverse("group_delete", args=[group.pk]))
        self.assertFalse(Group.objects.filter(pk=group.pk).exists())

    def test_crear_grupos_command(self):
        call_command("crear_grupos", stdout=open("/dev/null", "w"))
        self.assertEqual(
            set(Group.objects.values_list("name", flat=True)), {"Administración", "Cobranza", "Consulta"}
        )
        consulta = Group.objects.get(name="Consulta")
        ids = set(consulta.permissions.values_list("pk", flat=True))
        self.assertEqual(level_for(ids, "expense"), Level.READ)
        self.assertEqual(level_for(ids, "auth"), Level.NONE)


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password=PASSWORD)
        self.client.force_login(self.user)

    def test_any_user_can_open_profile(self):
        self.assertEqual(self.client.get(reverse("profile")).status_code, 200)

    def test_change_own_password_keeps_session(self):
        response = self.client.post(reverse("profile"), {
            "action": "password", "old_password": PASSWORD,
            "new_password1": "Nueva-Clave-2026", "new_password2": "Nueva-Clave-2026",
        })
        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Nueva-Clave-2026"))
        self.assertEqual(self.client.get(reverse("profile")).status_code, 200)

    def test_update_own_data(self):
        self.client.post(reverse("profile"), {"action": "profile", "first_name": "Ana", "last_name": "Pérez", "email": ""})
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), "Ana Pérez")
