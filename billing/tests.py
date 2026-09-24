from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from connection.models import Line
from customer.models import Customer

from .models import Account, Fee, Invoice, InvoiceLine


class InvoiceDetailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("admin", password="pass")
        self.client.force_login(self.user)
        customer = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=self.user)
        self.active_1 = Line.objects.create(customer=customer, created_by=self.user)
        self.active_2 = Line.objects.create(customer=customer, created_by=self.user)
        self.inactive = Line.objects.create(customer=customer, created_by=self.user, isActive=False)
        fee = Fee.objects.create(name="Mensual", amount=5, created_by=self.user)
        account = Account.objects.create(name="Principal", number="001", created_by=self.user)
        self.invoice = Invoice.objects.create(
            fee=fee,
            account=account,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            due_date=date(2026, 10, 10),
            created_by=self.user,
        )

    def _assign(self, line, is_paid=False):
        invoice_line = InvoiceLine(invoice=self.invoice, line=line, created_by=self.user, isPaid=is_paid)
        invoice_line.save()
        return invoice_line

    def test_list_links_to_detail(self):
        response = self.client.get(reverse("billing_home"))
        self.assertContains(response, reverse("invoice_detail", args=[self.invoice.pk]))

    def test_detail_shows_summary_and_lines(self):
        self._assign(self.active_1, is_paid=True)
        self._assign(self.active_2)
        response = self.client.get(reverse("invoice_detail", args=[self.invoice.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["lines_count"], 2)
        self.assertEqual(response.context["paid_count"], 1)
        self.assertEqual(response.context["collected_amount"], 5)
        self.assertEqual(response.context["expected_amount"], 10)
        self.assertContains(response, self.active_2.code)

    def test_assign_all_only_assigns_active_lines(self):
        self._assign(self.active_1)
        response = self.client.post(reverse("invoice_assign_lines", args=[self.invoice.pk]))
        self.assertEqual(response["HX-Trigger"], "invoiceLinesChanged")
        assigned = set(InvoiceLine.objects.filter(invoice=self.invoice).values_list("line_id", flat=True))
        self.assertEqual(assigned, {self.active_1.pk, self.active_2.pk})

    def test_assign_single_line(self):
        response = self.client.post(
            reverse("invoice_assign_line", args=[self.invoice.pk]), {"line": self.inactive.pk}
        )
        self.assertEqual(response["HX-Trigger"], "invoiceLinesChanged")
        self.assertTrue(InvoiceLine.objects.filter(invoice=self.invoice, line=self.inactive).exists())

    def test_assign_single_line_rejects_already_assigned(self):
        self._assign(self.active_1)
        response = self.client.post(
            reverse("invoice_assign_line", args=[self.invoice.pk]), {"line": self.active_1.pk}
        )
        self.assertFalse(response.has_header("HX-Trigger"))
        self.assertEqual(InvoiceLine.objects.filter(invoice=self.invoice).count(), 1)

    def test_lines_filter_by_status(self):
        self._assign(self.active_1, is_paid=True)
        self._assign(self.active_2)
        response = self.client.get(reverse("invoice_lines", args=[self.invoice.pk]), {"status": "paid"})
        self.assertEqual([il.line for il in response.context["invoice_lines"]], [self.active_1])

    def test_toggle_paid(self):
        invoice_line = self._assign(self.active_1)
        self.client.post(reverse("invoice_line_toggle_paid", args=[invoice_line.pk]))
        invoice_line.refresh_from_db()
        self.assertTrue(invoice_line.isPaid)

    def test_remove_pending_line_but_not_paid_line(self):
        pending = self._assign(self.active_1)
        paid = self._assign(self.active_2, is_paid=True)
        self.client.post(reverse("invoice_line_remove", args=[pending.pk]))
        self.client.post(reverse("invoice_line_remove", args=[paid.pk]))
        self.assertFalse(InvoiceLine.objects.filter(pk=pending.pk).exists())
        self.assertTrue(InvoiceLine.objects.filter(pk=paid.pk).exists())

    def test_delete_redirects_to_list(self):
        response = self.client.post(reverse("invoice_delete", args=[self.invoice.pk]))
        self.assertEqual(response["HX-Redirect"], reverse("billing_home"))
        self.assertFalse(Invoice.objects.exists())

    def test_print_single_receipt(self):
        invoice_line = self._assign(self.active_1)
        response = self.client.get(reverse("invoice_line_print_receipt", args=[invoice_line.pk]))
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_print_select_modal_lists_lines(self):
        self._assign(self.active_1)
        response = self.client.get(reverse("invoice_print_select", args=[self.invoice.pk]))
        self.assertContains(response, self.active_1.code)

    def test_print_selected_only_prints_chosen_lines(self):
        chosen = self._assign(self.active_1)
        self._assign(self.active_2)
        response = self.client.get(
            reverse("invoice_print_selected", args=[self.invoice.pk]), {"ids": [chosen.pk]}
        )
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_print_selected_with_nothing_chosen_redirects(self):
        self._assign(self.active_1)
        response = self.client.get(reverse("invoice_print_selected", args=[self.invoice.pk]))
        self.assertRedirects(response, reverse("invoice_detail", args=[self.invoice.pk]))
