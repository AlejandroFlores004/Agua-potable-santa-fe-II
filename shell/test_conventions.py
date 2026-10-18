"""Tests transversales: páginas de error y convenciones comunes a todas las vistas."""
from datetime import date

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.views import defaults
from django.views.csrf import csrf_failure

from billing.models import Account, Fee, Invoice, InvoiceLine, LateFee
from connection.models import Line
from customer.models import Customer
from expense.models import Expense, RecurringExpense

# Páginas completas que solo puede ver un usuario con sesión.
LIST_PAGES = ["home", "customer_home", "mechas", "billing_home", "fee_home", "expense_home", "recurring_home"]


class ErrorPagesTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")

    @override_settings(DEBUG=False)
    def test_unknown_url_uses_404_page(self):
        response = self.client.get("/esta-pagina-no-existe/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Página no encontrada", status_code=404)

    @override_settings(DEBUG=False)
    def test_missing_record_uses_404_page(self):
        user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(user)
        response = self.client.get(reverse("invoice_detail", args=[999]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_400_page(self):
        response = defaults.bad_request(self.request, Exception())
        self.assertEqual(response.status_code, 400)
        self.assertIn("Solicitud no válida", response.content.decode())

    def test_500_page_renders_without_context(self):
        response = defaults.server_error(self.request)
        self.assertEqual(response.status_code, 500)
        self.assertIn("Algo salió mal", response.content.decode())

    def test_403_page_generic(self):
        response = defaults.permission_denied(self.request, Exception())
        self.assertEqual(response.status_code, 403)
        self.assertIn("no tiene permiso para ver esta página", response.content.decode())

    def test_403_page_names_module_and_action(self):
        # Contrato con accounts.middleware.ModulePermissionMiddleware.
        html = render_to_string("403.html", {"module": "Gastos", "action": "modificar"})
        self.assertIn("no tiene permiso para modificar <strong>Gastos</strong>", html)

    def test_csrf_failure_page(self):
        response = csrf_failure(self.request)
        self.assertEqual(response.status_code, 403)
        self.assertIn("La página expiró", response.content.decode())

    def test_error_pages_are_in_spanish(self):
        for template in ["400.html", "403.html", "403_csrf.html", "404.html", "500.html"]:
            with self.subTest(template=template):
                html = render_to_string(template)
                self.assertIn('lang="es"', html)
                self.assertIn("Ir al inicio", html)


class LoginRequiredTests(TestCase):
    def test_pages_redirect_anonymous_users_to_login(self):
        for name in LIST_PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login")))

    def test_actions_redirect_anonymous_users_to_login(self):
        response = self.client.post(reverse("customer_delete", args=[1]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))


class ViewConventionsTests(TestCase):
    """Todas las apps deben comportarse igual: mismas respuestas, mensajes y confirmaciones."""

    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=self.user)
        self.fee = Fee.objects.create(name="Mensual", amount=5, created_by=self.user)
        self.line = Line.objects.create(customer=self.customer, fee=self.fee, created_by=self.user)
        self.late_fee = LateFee.objects.create(name="Mora", amount=1, created_by=self.user)
        account = Account.objects.create(name="Principal", number="001", created_by=self.user)
        self.invoice = Invoice.objects.create(
            account=account,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            due_date=date(2026, 10, 10),
            created_by=self.user,
        )
        self.invoice_line = InvoiceLine(invoice=self.invoice, line=self.line, created_by=self.user)
        self.invoice_line.save()
        self.expense = Expense.objects.create(concept="Cloro", amount=10, date=date(2026, 9, 5), created_by=self.user)
        self.plan = RecurringExpense.objects.create(
            name="Luz", amount=20, start_date=date(2026, 9, 1), created_by=self.user
        )

    def _post_only_urls(self):
        return [
            reverse("customer_delete", args=[self.customer.pk]),
            reverse("line_toggle", args=[self.line.pk]),
            reverse("fee_toggle", args=[self.fee.pk]),
            reverse("late_fee_make_default", args=[self.late_fee.pk]),
            reverse("invoice_delete", args=[self.invoice.pk]),
            reverse("invoice_assign_lines", args=[self.invoice.pk]),
            reverse("invoice_line_toggle_paid", args=[self.invoice_line.pk]),
            reverse("invoice_line_remove", args=[self.invoice_line.pk]),
            reverse("expense_delete", args=[self.expense.pk]),
            reverse("recurring_toggle", args=[self.plan.pk]),
            reverse("recurring_delete", args=[self.plan.pk]),
        ]

    def test_destructive_actions_reject_get(self):
        for url in self._post_only_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_actions_answer_with_oob_messages_and_trigger(self):
        cases = [
            (reverse("line_toggle", args=[self.line.pk]), "lineSaved", "Mecha desactivada correctamente."),
            (reverse("fee_toggle", args=[self.fee.pk]), "feeSaved", "Cuota desactivada correctamente."),
            (
                reverse("late_fee_make_default", args=[self.late_fee.pk]),
                "lateFeeSaved",
                "La mora «Mora» ahora es la mora por defecto.",
            ),
            (reverse("expense_delete", args=[self.expense.pk]), "expenseSaved", "Gasto eliminado correctamente."),
            (
                reverse("recurring_toggle", args=[self.plan.pk]),
                "recurringSaved",
                "Gasto recurrente desactivado correctamente.",
            ),
            (
                reverse("customer_delete", args=[self.customer.pk]),
                "customerSaved",
                "No se puede eliminar un cliente con mechas.",
            ),
        ]
        for url, trigger, message in cases:
            with self.subTest(url=url):
                response = self.client.post(url, HTTP_HX_REQUEST="true")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["HX-Trigger"], trigger)
                self.assertTemplateUsed(response, "partials/base/_messages_oob.html")
                self.assertContains(response, 'id="messages-container" hx-swap-oob="true"')
                self.assertContains(response, message)

    def test_success_and_error_messages_use_matching_alerts(self):
        response = self.client.post(reverse("line_toggle", args=[self.line.pk]))
        self.assertContains(response, "alert-success")
        response = self.client.post(reverse("customer_delete", args=[self.customer.pk]))
        self.assertContains(response, "alert-error")

    def test_base_layout_includes_global_confirm_modal(self):
        response = self.client.get(reverse("customer_home"))
        self.assertTemplateUsed(response, "partials/base/_confirm_modal.html")
        self.assertContains(response, 'id="confirm-modal"')
        self.assertContains(response, "htmx:confirm")
        self.assertContains(response, "htmx:responseError")
        self.assertContains(response, '<html lang="es"')

    def test_list_pages_return_only_the_table_for_htmx(self):
        partials = {
            "customer_home": "partials/customer/_customer_table.html",
            "mechas": "partials/line/_line_table.html",
            "billing_home": "partials/invoice/_invoice_table.html",
            "fee_home": "partials/fee/_fee_table.html",
            "expense_home": "partials/expense/_expense_table.html",
            "recurring_home": "partials/recurring/_recurring_table.html",
        }
        for name, partial in partials.items():
            with self.subTest(page=name):
                full = self.client.get(reverse(name))
                self.assertEqual(full.status_code, 200)
                self.assertTemplateUsed(full, "base.html")

                fragment = self.client.get(reverse(name), HTTP_HX_REQUEST="true")
                self.assertEqual(fragment.status_code, 200)
                self.assertTemplateUsed(fragment, partial)
                self.assertTemplateNotUsed(fragment, "base.html")

    def test_list_pages_survive_invalid_page_number(self):
        for name in LIST_PAGES[1:]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name), {"page": "abc"}).status_code, 200)
                self.assertEqual(self.client.get(reverse(name), {"page": "999"}).status_code, 200)

    def test_missing_records_return_404(self):
        urls = [
            reverse("customer_edit", args=[999]),
            reverse("line_edit", args=[999]),
            reverse("invoice_edit", args=[999]),
            reverse("expense_edit", args=[999]),
            reverse("recurring_edit", args=[999]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_confirm_questions_use_guillemets_not_html_quotes(self):
        response = self.client.get(reverse("fee_home"))
        self.assertContains(response, "¿Desactivar la cuota «Mensual»?")
        self.assertNotContains(response, "&quot;Mensual&quot;")
