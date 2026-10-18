from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customer.models import Customer

from .forms import LineForm
from .models import Line


class LineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=self.user)
        self.line = Line.objects.create(customer=self.customer, created_by=self.user)

    def test_toggle_deactivates_and_reactivates_without_deleting(self):
        self.client.post(reverse("line_toggle", args=[self.line.pk]))
        self.line.refresh_from_db()
        self.assertFalse(self.line.isActive)

        self.client.post(reverse("line_toggle", args=[self.line.pk]))
        self.line.refresh_from_db()
        self.assertTrue(self.line.isActive)

    def test_edit_cannot_change_customer(self):
        other = Customer.objects.create(firstName="Luis", lastName="Gómez", created_by=self.user)
        form = LineForm({"customer": other.pk}, instance=self.line)
        self.assertTrue(form.fields["customer"].disabled)
        form.is_valid()
        self.assertEqual(form.cleaned_data["customer"], self.customer)

    def test_customer_with_lines_cannot_be_deleted(self):
        self.client.post(reverse("customer_delete", args=[self.customer.pk]))
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())
        self.assertTrue(Line.objects.filter(pk=self.line.pk).exists())

    def test_customer_without_lines_can_be_deleted(self):
        empty = Customer.objects.create(firstName="Sin", lastName="Mechas", created_by=self.user)
        self.client.post(reverse("customer_delete", args=[empty.pk]))
        self.assertFalse(Customer.objects.filter(pk=empty.pk).exists())
