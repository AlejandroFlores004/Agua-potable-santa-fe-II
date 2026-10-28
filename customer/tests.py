from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from connection.models import Line, Location

from .models import Customer


def customer_data(**overrides):
    data = {
        "dui": "",
        "firstName": "Ana",
        "lastName": "Pérez",
        "email": "",
        "number": "7777-7777",
        "lines-TOTAL_FORMS": "1",
        "lines-INITIAL_FORMS": "0",
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
        "lines-0-location": "",
        "lines-0-description": "",
    }
    data.update(overrides)
    return data


class CustomerViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(self.user)

    def test_home_lists_and_searches(self):
        Customer.objects.create(firstName="Ana", lastName="Pérez", dui="01234567-8", created_by=self.user)
        Customer.objects.create(firstName="Luis", lastName="Gómez", created_by=self.user)

        response = self.client.get(reverse("customer_home"))
        self.assertContains(response, "Ana")
        self.assertContains(response, "Luis")

        response = self.client.get(reverse("customer_home"), {"q": "01234567"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Ana")
        self.assertNotContains(response, "Luis")

    def test_empty_search_message(self):
        response = self.client.get(reverse("customer_home"), {"q": "nadie"}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<table")

    def test_create_form_renders_modal_with_one_empty_line(self):
        response = self.client.get(reverse("customer_create"))
        self.assertTemplateUsed(response, "partials/customer/_customer_form_modal.html")
        self.assertEqual(response.context["formset"].total_form_count(), 1)

    def test_create_customer_without_line(self):
        response = self.client.post(reverse("customer_create"), customer_data())
        self.assertEqual(response["HX-Trigger"], "customerSaved")
        self.assertContains(response, "Cliente creado correctamente.")
        customer = Customer.objects.get()
        self.assertEqual(customer.created_by, self.user)
        self.assertFalse(customer.lines.exists())

    def test_create_customer_with_line(self):
        location = Location.objects.create(name="Centro")
        self.client.post(
            reverse("customer_create"),
            customer_data(**{"lines-0-location": location.pk, "lines-0-description": "Casa"}),
        )
        line = Line.objects.get()
        self.assertEqual(line.customer.firstName, "Ana")
        self.assertEqual(line.created_by, self.user)
        self.assertEqual(line.location, location)
        self.assertTrue(line.isActive)
        # El código se genera con las iniciales del cliente y el id de la mecha.
        self.assertEqual(line.code, f"AP{line.pk:04d}")

    def test_invalid_form_returns_modal_with_errors(self):
        response = self.client.post(reverse("customer_create"), customer_data(firstName=""))
        self.assertTemplateUsed(response, "partials/customer/_customer_form_modal.html")
        self.assertFalse(response.has_header("HX-Trigger"))
        self.assertFalse(Customer.objects.exists())

    def test_duplicate_dui_is_rejected(self):
        Customer.objects.create(firstName="Otro", lastName="Cliente", dui="01234567-8", created_by=self.user)
        response = self.client.post(reverse("customer_create"), customer_data(dui="01234567-8"))
        self.assertTrue(response.context["form"].errors.get("dui"))
        self.assertEqual(Customer.objects.count(), 1)

    def test_edit_keeps_creator(self):
        other = User.objects.create_user("otro", password="pass")
        customer = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=other)
        data = customer_data(lastName="López", **{"lines-TOTAL_FORMS": "0"})
        response = self.client.post(reverse("customer_edit", args=[customer.pk]), data)
        self.assertContains(response, "Cliente actualizado correctamente.")
        customer.refresh_from_db()
        self.assertEqual(customer.lastName, "López")
        self.assertEqual(customer.created_by, other)

    def test_delete_customer_without_lines(self):
        customer = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=self.user)
        response = self.client.post(reverse("customer_delete", args=[customer.pk]))
        self.assertContains(response, "Cliente eliminado correctamente.")
        self.assertFalse(Customer.objects.exists())


class CustomerValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(self.user)

    def _create(self, **overrides):
        return self.client.post(reverse("customer_create"), customer_data(**overrides), HTTP_HX_REQUEST="true")

    def test_valid_dui_saves_without_warning(self):
        response = self._create(dui="00870139-1")
        self.assertTrue(Customer.objects.filter(dui="00870139-1").exists())
        self.assertContains(response, "Cliente creado correctamente.")
        self.assertNotContains(response, "alert-warning")

    def test_missing_dui_saves_with_warning(self):
        response = self._create(dui="")
        self.assertEqual(Customer.objects.count(), 1)
        self.assertContains(response, "El cliente no tiene DUI")

    def test_badly_formatted_dui_saves_with_warning(self):
        response = self._create(dui="0267179-0")
        self.assertTrue(Customer.objects.filter(dui="0267179-0").exists())
        self.assertContains(response, "El DUI debe tener el formato 00000000-0.")

    def test_wrong_check_digit_saves_with_warning(self):
        response = self._create(dui="05052625-6")
        self.assertTrue(Customer.objects.filter(dui="05052625-6").exists())
        self.assertContains(response, "El DUI no es válido")

    def test_invalid_phone_is_rejected(self):
        for number in ["123", "abcd-efgh"]:
            with self.subTest(number=number):
                response = self._create(number=number)
                self.assertEqual(Customer.objects.count(), 0)
                self.assertContains(response, "al menos 8 dígitos")

    def test_valid_phone_formats_are_accepted(self):
        for index, number in enumerate(["7000-0000", "+503 7000 0000"]):
            with self.subTest(number=number):
                self._create(number=number, firstName=f"Ana{index}")
        self.assertEqual(Customer.objects.count(), 2)


class CustomerDetailTests(TestCase):
    def setUp(self):
        from datetime import date

        from billing.models import Account, Fee, Invoice, InvoiceLine

        self.user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=self.user)
        fee = Fee.objects.create(name="Básica", amount=5, created_by=self.user)
        self.line = Line.objects.create(customer=self.customer, fee=fee, created_by=self.user)
        Line.objects.create(customer=self.customer, created_by=self.user)
        account = Account.objects.create(name="Caja", number="1", created_by=self.user)

        def invoice(month, status):
            return Invoice.objects.create(
                account=account, start_date=date(2026, month, 1), end_date=date(2026, month, 28),
                due_date=date(2026, month, 28), status=status, created_by=self.user,
            )

        self.paid = InvoiceLine.objects.create(
            invoice=invoice(1, Invoice.Status.CLOSED), line=self.line, isPaid=True, created_by=self.user
        )
        self.overdue = InvoiceLine.objects.create(
            invoice=invoice(2, Invoice.Status.CLOSED), line=self.line, created_by=self.user
        )
        self.pending = InvoiceLine.objects.create(
            invoice=invoice(3, Invoice.Status.OPEN), line=self.line, created_by=self.user
        )

    def test_detail_shows_lines_and_receipts(self):
        response = self.client.get(reverse("customer_detail", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customer_detail.html")
        lines = response.context["lines"]
        self.assertEqual(len(lines), 2)
        line = next(l for l in lines if l.pk == self.line.pk)
        self.assertEqual([r.pk for r in line.receipts], [self.pending.pk, self.overdue.pk, self.paid.pk])
        self.assertContains(response, self.paid.code)
        self.assertContains(response, "Esta línea todavía no tiene recibos.")

    def test_totals_ignore_carried_receipts(self):
        context = self.client.get(reverse("customer_detail", args=[self.customer.pk])).context
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.carried_to, self.pending)
        # El vencido se trasladó al pendiente (5 + 5 de saldo anterior + mora si hay).
        self.assertEqual(context["pending_total"], self.pending.total)
        self.assertEqual(context["overdue_total"], 0)
        self.assertEqual(context["paid_total"], self.paid.total)
        self.assertEqual(context["receipts_count"], 3)

    def test_unknown_customer_is_404(self):
        response = self.client.get(reverse("customer_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_table_links_to_detail(self):
        response = self.client.get(reverse("customer_home"))
        self.assertContains(response, reverse("customer_detail", args=[self.customer.pk]))
