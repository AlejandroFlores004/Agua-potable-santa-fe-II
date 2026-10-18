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
