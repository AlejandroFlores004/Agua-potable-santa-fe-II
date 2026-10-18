from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from billing.models import Fee
from customer.models import Customer

from .models import Line, Location


class LineViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=self.user)
        self.fee = Fee.objects.create(name="Mensual", amount=5, created_by=self.user)
        self.location = Location.objects.create(name="Centro")

    def test_create_requires_fee(self):
        response = self.client.post(reverse("line_create"), {"customer": self.customer.pk})
        self.assertTemplateUsed(response, "partials/line/_line_form_modal.html")
        self.assertTrue(response.context["form"].errors.get("fee"))
        self.assertFalse(Line.objects.exists())

    def test_create_line(self):
        response = self.client.post(
            reverse("line_create"),
            {"customer": self.customer.pk, "fee": self.fee.pk, "location": self.location.pk},
        )
        self.assertEqual(response["HX-Trigger"], "lineSaved")
        self.assertContains(response, "Mecha creada correctamente.")
        line = Line.objects.get()
        self.assertEqual(line.created_by, self.user)
        self.assertEqual(line.code, f"AP{line.pk:04d}")

    def test_edit_line(self):
        line = Line.objects.create(customer=self.customer, fee=self.fee, created_by=self.user)
        response = self.client.post(
            reverse("line_edit", args=[line.pk]),
            {"fee": self.fee.pk, "location": self.location.pk, "description": "Nueva"},
        )
        self.assertContains(response, "Mecha actualizada correctamente.")
        line.refresh_from_db()
        self.assertEqual(line.description, "Nueva")
        self.assertEqual(line.location, self.location)

    def test_inactive_fee_is_not_offered_for_new_lines(self):
        Fee.objects.create(name="Vieja", amount=3, isActive=False, created_by=self.user)
        response = self.client.get(reverse("line_create"))
        self.assertNotIn("Vieja", [fee.name for fee in response.context["form"].fields["fee"].queryset])

    def test_search(self):
        Line.objects.create(customer=self.customer, fee=self.fee, location=self.location, created_by=self.user)
        other = Customer.objects.create(firstName="Luis", lastName="Gómez", created_by=self.user)
        Line.objects.create(customer=other, fee=self.fee, created_by=self.user)

        response = self.client.get(reverse("mechas"), {"q": "Centro"}, HTTP_HX_REQUEST="true")
        self.assertEqual(len(response.context["lines"]), 1)
        self.assertEqual(response.context["lines"][0].customer, self.customer)

    def test_mechas_page_uses_mechas_wording(self):
        response = self.client.get(reverse("mechas"))
        self.assertTemplateUsed(response, "mechas_home.html")
        self.assertContains(response, "Nueva mecha")
