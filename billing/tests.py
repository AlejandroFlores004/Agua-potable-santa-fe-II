from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from connection.models import Line
from customer.models import Customer

from .models import Account, Fee, Invoice, InvoiceLine, LateFee


class InvoiceDetailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(self.user)
        customer = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=self.user)
        self.fee = Fee.objects.create(name="Mensual", amount=5, created_by=self.user)
        self.active_1 = Line.objects.create(customer=customer, fee=self.fee, created_by=self.user)
        self.active_2 = Line.objects.create(customer=customer, fee=self.fee, created_by=self.user)
        self.inactive = Line.objects.create(customer=customer, fee=self.fee, created_by=self.user, isActive=False)
        account = Account.objects.create(name="Principal", number="001", created_by=self.user)
        self.invoice = Invoice.objects.create(
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

    def test_assign_uses_each_line_fee(self):
        premium = Fee.objects.create(name="Comercial", amount=12, created_by=self.user)
        self.active_2.fee = premium
        self.active_2.save()
        self.client.post(reverse("invoice_assign_lines", args=[self.invoice.pk]))
        amounts = dict(InvoiceLine.objects.filter(invoice=self.invoice).values_list("line_id", "amount"))
        self.assertEqual(amounts, {self.active_1.pk: 5, self.active_2.pk: 12})
        response = self.client.get(reverse("invoice_detail", args=[self.invoice.pk]))
        self.assertEqual(response.context["expected_amount"], 17)

    def test_assign_all_skips_lines_without_fee(self):
        self.active_2.fee = None
        self.active_2.save()
        self.client.post(reverse("invoice_assign_lines", args=[self.invoice.pk]))
        assigned = set(InvoiceLine.objects.filter(invoice=self.invoice).values_list("line_id", flat=True))
        self.assertEqual(assigned, {self.active_1.pk})

    def test_assigned_amount_does_not_change_with_line_fee(self):
        invoice_line = self._assign(self.active_1)
        self.active_1.fee = Fee.objects.create(name="Nueva", amount=20, created_by=self.user)
        self.active_1.save()
        self.fee.amount = 8
        self.fee.save()
        invoice_line.refresh_from_db()
        self.assertEqual(invoice_line.amount, 5)

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
        self.invoice.open()
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


class FeeToggleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=self.user)
        self.fee = Fee.objects.create(name="Mensual", amount=5, created_by=self.user)

    def test_toggle_deactivates_and_reactivates_without_deleting(self):
        line = Line.objects.create(customer=self.customer, fee=self.fee, created_by=self.user)
        self.client.post(reverse("fee_toggle", args=[self.fee.pk]))
        self.fee.refresh_from_db()
        line.refresh_from_db()
        self.assertFalse(self.fee.isActive)
        self.assertEqual(line.fee, self.fee)

        self.client.post(reverse("fee_toggle", args=[self.fee.pk]))
        self.fee.refresh_from_db()
        self.assertTrue(self.fee.isActive)

    def test_line_form_only_offers_active_fees_except_current(self):
        from connection.forms import LineForm

        inactive = Fee.objects.create(name="Vieja", amount=3, created_by=self.user, isActive=False)
        self.assertNotIn(inactive, LineForm().fields["fee"].queryset)

        line = Line.objects.create(customer=self.customer, fee=inactive, created_by=self.user)
        self.assertIn(inactive, LineForm(instance=line).fields["fee"].queryset)


class LateFeeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(self.user)
        customer = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=self.user)
        self.fee = Fee.objects.create(name="Mensual", amount=5, created_by=self.user)
        self.line = Line.objects.create(customer=customer, fee=self.fee, created_by=self.user)
        self.account = Account.objects.create(name="Principal", number="001", created_by=self.user)
        self.september = self._invoice(9)
        self.october = self._invoice(10)
        self.late_fee = LateFee.objects.create(name="Mora", amount=2, isDefault=True, created_by=self.user)

    def _invoice(self, month):
        return Invoice.objects.create(
            account=self.account,
            start_date=date(2026, month, 1),
            end_date=date(2026, month, 28),
            due_date=date(2026, month + 1, 10),
            created_by=self.user,
        )

    def _assign(self, invoice, is_paid=False):
        invoice_line = InvoiceLine(invoice=invoice, line=self.line, created_by=self.user, isPaid=is_paid)
        invoice_line.save()
        return invoice_line

    def test_paid_previous_receipt_adds_nothing(self):
        self._assign(self.september, is_paid=True)
        october_line = self._assign(self.october)
        self.assertEqual(october_line.previous_balance, 0)
        self.assertEqual(october_line.late_fee_amount, 0)
        self.assertEqual(october_line.total, 5)

    def test_unpaid_previous_receipt_carries_balance_plus_default_late_fee(self):
        september_line = self._assign(self.september)
        october_line = self._assign(self.october)
        self.assertEqual(october_line.previous_balance, 5)
        self.assertEqual(october_line.late_fee, self.late_fee)
        self.assertEqual(october_line.total, 12)
        september_line.refresh_from_db()
        self.assertEqual(september_line.carried_to, october_line)

    def test_carry_over_accumulates_across_months(self):
        self._assign(self.september)
        self._assign(self.october)
        november_line = self._assign(self._invoice(11))
        # 5 + 2 de septiembre-octubre, + 5 de octubre, + 2 de mora nueva + 5 de noviembre
        self.assertEqual(november_line.previous_balance, 12)
        self.assertEqual(november_line.total, 19)

    def test_changing_default_only_affects_new_receipts(self):
        self._assign(self.september)
        october_line = self._assign(self.october)
        higher = LateFee.objects.create(name="Mora alta", amount=4, created_by=self.user)
        self.client.post(reverse("late_fee_make_default", args=[higher.pk]))
        self.late_fee.refresh_from_db()
        self.assertFalse(self.late_fee.isDefault)
        self.assertEqual(LateFee.get_default(), higher)

        october_line.refresh_from_db()
        self.assertEqual(october_line.late_fee_amount, 2)
        november_line = self._assign(self._invoice(11))
        self.assertEqual(november_line.late_fee_amount, 4)

    def test_create_late_fee_as_default(self):
        self.client.post(reverse("late_fee_create"), {"name": "Nueva", "amount": "3", "make_default": "on"})
        self.assertEqual(LateFee.get_default().name, "Nueva")
        self.assertEqual(LateFee.objects.filter(isDefault=True).count(), 1)

    def test_override_late_fee_on_single_receipt(self):
        self._assign(self.september)
        october_line = self._assign(self.october)
        custom = LateFee.objects.create(name="Especial", amount=1, created_by=self.user)
        response = self.client.post(reverse("invoice_line_late_fee", args=[october_line.pk]), {"late_fee": custom.pk})
        self.assertEqual(response["HX-Trigger"], "invoiceLinesChanged")
        october_line.refresh_from_db()
        self.assertEqual(october_line.late_fee_amount, 1)
        self.assertEqual(october_line.total, 11)

        self.client.post(reverse("invoice_line_late_fee", args=[october_line.pk]), {"late_fee": ""})
        october_line.refresh_from_db()
        self.assertEqual(october_line.total, 10)

    def test_carried_receipt_cannot_be_paid_or_removed(self):
        september_line = self._assign(self.september)
        self._assign(self.october)
        self.client.post(reverse("invoice_line_toggle_paid", args=[september_line.pk]))
        self.client.post(reverse("invoice_line_remove", args=[september_line.pk]))
        september_line.refresh_from_db()
        self.assertFalse(september_line.isPaid)

    def test_removing_new_receipt_restores_previous_as_pending(self):
        september_line = self._assign(self.september)
        october_line = self._assign(self.october)
        self.client.post(reverse("invoice_line_remove", args=[october_line.pk]))
        september_line.refresh_from_db()
        self.assertIsNone(september_line.carried_to)

    def test_summary_excludes_carried_receipts(self):
        self._assign(self.september)
        self._assign(self.october, is_paid=True)
        september = self.client.get(reverse("invoice_detail", args=[self.september.pk])).context
        self.assertEqual(september["pending_count"], 0)
        self.assertEqual(september["carried_count"], 1)
        self.assertEqual(september["expected_amount"], 0)
        october = self.client.get(reverse("invoice_detail", args=[self.october.pk])).context
        self.assertEqual(october["collected_amount"], 12)

    def test_receipt_pdf_with_late_fee(self):
        self._assign(self.september)
        october_line = self._assign(self.october)
        response = self.client.get(reverse("invoice_line_print_receipt", args=[october_line.pk]))
        self.assertEqual(response["Content-Type"], "application/pdf")


class InvoiceStatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(self.user)
        customer = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=self.user)
        fee = Fee.objects.create(name="Mensual", amount=5, created_by=self.user)
        self.line = Line.objects.create(customer=customer, fee=fee, created_by=self.user)
        self.account = Account.objects.create(name="Principal", number="001", created_by=self.user)
        self.september = self._invoice(9)
        self.october = self._invoice(10)

    def _invoice(self, month):
        return Invoice.objects.create(
            account=self.account,
            start_date=date(2026, month, 1),
            end_date=date(2026, month, 28),
            due_date=date(2026, month + 1, 10),
            created_by=self.user,
        )

    def _assign(self, invoice):
        invoice_line = InvoiceLine(invoice=invoice, line=self.line, created_by=self.user)
        invoice_line.save()
        return invoice_line

    def test_open_and_close_show_confirmation_modal(self):
        self._assign(self.september)
        response = self.client.get(reverse("invoice_open", args=[self.september.pk]))
        self.assertContains(response, reverse("invoice_open", args=[self.september.pk]))
        self.september.refresh_from_db()
        self.assertTrue(self.september.is_draft)

        self.september.open()
        response = self.client.get(reverse("invoice_close", args=[self.september.pk]))
        self.assertContains(response, "Quedarán vencidos")
        self.assertEqual(response.context["pending_count"], 1)
        self.september.refresh_from_db()
        self.assertTrue(self.september.is_open)

    def test_new_invoice_starts_as_draft(self):
        self.assertEqual(self.september.status, Invoice.Status.DRAFT)

    def test_open_and_close(self):
        self._assign(self.september)
        detail = reverse("invoice_detail", args=[self.september.pk])
        self.assertContains(self.client.get(detail), "Abrir factura")
        self.assertNotContains(self.client.get(detail), "Marcar pagada")
        self.client.post(reverse("invoice_open", args=[self.september.pk]))
        self.september.refresh_from_db()
        self.assertTrue(self.september.is_open)
        self.assertContains(self.client.get(detail), "Cerrar factura")
        self.assertContains(self.client.get(detail), "Marcar pagada")
        response = self.client.post(reverse("invoice_close", args=[self.september.pk]))
        self.assertIn("invoiceLinesChanged", response["HX-Trigger"])
        self.september.refresh_from_db()
        self.assertTrue(self.september.is_closed)

    def test_cannot_open_while_another_is_open(self):
        self.september.open()
        self.client.post(reverse("invoice_open", args=[self.october.pk]))
        self.october.refresh_from_db()
        self.assertTrue(self.october.is_draft)

        self.september.close()
        self.client.post(reverse("invoice_open", args=[self.october.pk]))
        self.october.refresh_from_db()
        self.assertTrue(self.october.is_open)

    def test_closed_invoice_cannot_be_reopened(self):
        self.september.open()
        self.september.close()
        self.client.post(reverse("invoice_open", args=[self.september.pk]))
        self.september.refresh_from_db()
        self.assertTrue(self.september.is_closed)

    def test_database_rejects_two_open_invoices(self):
        from django.db import IntegrityError, transaction

        self.september.open()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Invoice.objects.filter(pk=self.october.pk).update(status=Invoice.Status.OPEN)

    def test_paid_receipt_cannot_be_unmarked_after_close(self):
        invoice_line = self._assign(self.september)
        self.september.open()
        self.client.post(reverse("invoice_line_toggle_paid", args=[invoice_line.pk]))
        self.september.close()
        self.client.post(reverse("invoice_line_toggle_paid", args=[invoice_line.pk]))
        invoice_line.refresh_from_db()
        self.assertTrue(invoice_line.isPaid)

    def test_draft_cannot_be_paid(self):
        invoice_line = self._assign(self.september)
        self.client.post(reverse("invoice_line_toggle_paid", args=[invoice_line.pk]))
        invoice_line.refresh_from_db()
        self.assertFalse(invoice_line.isPaid)

    def test_closed_invoice_receipts_cannot_change(self):
        unpaid = self._assign(self.september)
        self.september.open()
        self.september.close()
        self.client.post(reverse("invoice_line_toggle_paid", args=[unpaid.pk]))
        unpaid.refresh_from_db()
        self.assertFalse(unpaid.isPaid)
        self.assertContains(self.client.get(reverse("invoice_detail", args=[self.september.pk])), "Vencido")

        invoice_line = unpaid
        self.client.post(reverse("invoice_line_remove", args=[invoice_line.pk]))
        self.assertTrue(InvoiceLine.objects.filter(pk=invoice_line.pk).exists())
        self.client.post(reverse("invoice_assign_lines", args=[self.september.pk]))
        self.assertEqual(InvoiceLine.objects.filter(invoice=self.september).count(), 1)

    def test_draft_cannot_assign_lines_while_another_is_open(self):
        self.september.open()
        self.client.post(reverse("invoice_assign_lines", args=[self.october.pk]))
        self.assertFalse(InvoiceLine.objects.filter(invoice=self.october).exists())

        self.september.close()
        self.client.post(reverse("invoice_assign_lines", args=[self.october.pk]))
        self.assertTrue(InvoiceLine.objects.filter(invoice=self.october).exists())

    def test_open_invoice_still_accepts_new_lines(self):
        self.september.open()
        self.client.post(reverse("invoice_assign_lines", args=[self.september.pk]))
        self.assertTrue(InvoiceLine.objects.filter(invoice=self.september).exists())
