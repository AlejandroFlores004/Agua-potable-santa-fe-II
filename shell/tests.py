from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from billing.models import Account, Fee, Invoice, InvoiceLine
from connection.models import Line, Location
from customer.models import Customer


class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(self.user)
        self.ana = Customer.objects.create(firstName="Ana", lastName="Pérez", created_by=self.user)
        self.luis = Customer.objects.create(firstName="Luis", lastName="Gómez", created_by=self.user)
        Customer.objects.create(firstName="Sin", lastName="Línea", created_by=self.user)
        fee = Fee.objects.create(name="Mensual", amount=5, created_by=self.user)
        centro = Location.objects.create(name="Centro")
        self.line_1 = Line.objects.create(customer=self.ana, fee=fee, location=centro, created_by=self.user)
        self.line_2 = Line.objects.create(customer=self.ana, fee=fee, created_by=self.user)
        self.line_3 = Line.objects.create(customer=self.luis, created_by=self.user)
        Line.objects.create(customer=self.luis, fee=fee, created_by=self.user, isActive=False)
        account = Account.objects.create(name="Principal", number="001", created_by=self.user)
        self.old_invoice = Invoice.objects.create(
            account=account,
            start_date=date(2000, 1, 1),
            end_date=date(2000, 1, 31),
            due_date=date(2000, 2, 10),
            created_by=self.user,
        )
        self.new_invoice = Invoice.objects.create(
            account=account,
            start_date=date(2999, 1, 1),
            end_date=date(2999, 1, 31),
            due_date=date(2999, 2, 10),
            created_by=self.user,
        )
        self.old_invoice.open()
        self.old_invoice.close()
        self._assign(self.old_invoice, self.line_1, is_paid=True)
        self._assign(self.old_invoice, self.line_2)
        self._assign(self.new_invoice, self.line_1, is_paid=True)
        self._assign(self.new_invoice, self.line_2)

    def _assign(self, invoice, line, is_paid=False):
        InvoiceLine(invoice=invoice, line=line, created_by=self.user, isPaid=is_paid).save()

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)

    def test_counts(self):
        ctx = self.client.get(reverse("home")).context
        self.assertEqual(ctx["customers_total"], 3)
        self.assertEqual(ctx["customers_without_lines"], 1)
        self.assertEqual(ctx["lines_total"], 4)
        self.assertEqual(ctx["lines_active"], 3)
        self.assertEqual(ctx["lines_active_without_fee"], 1)

    def test_pending_and_overdue_amounts(self):
        ctx = self.client.get(reverse("home")).context
        self.assertEqual(ctx["pending_count"], 2)
        self.assertEqual(ctx["pending_amount"], Decimal("10"))
        # Only the receipt from the invoice whose due date has passed is overdue.
        self.assertEqual(ctx["overdue_count"], 1)
        self.assertEqual(ctx["overdue_amount"], Decimal("5"))

    def test_open_invoice_past_due_date_is_not_overdue(self):
        # Mientras está abierta todavía se reciben comprobantes, aunque ya pasó la fecha.
        Invoice.objects.filter(pk=self.old_invoice.pk).update(status=Invoice.Status.OPEN)
        ctx = self.client.get(reverse("home")).context
        self.assertEqual(ctx["overdue_count"], 0)

    def test_draft_invoice_is_never_overdue(self):
        Invoice.objects.filter(pk=self.old_invoice.pk).update(status=Invoice.Status.DRAFT)
        ctx = self.client.get(reverse("home")).context
        self.assertEqual(ctx["overdue_count"], 0)
        self.assertFalse(next(i for i in ctx["recent_invoices"] if i == self.old_invoice).is_overdue)

    def test_latest_invoice_summary(self):
        latest = self.client.get(reverse("home")).context["latest_invoice"]
        self.assertEqual(latest, self.new_invoice)
        self.assertEqual(latest.lines_count, 2)
        self.assertEqual(latest.paid_count, 1)
        self.assertEqual(latest.pending_count, 1)
        self.assertEqual(latest.collected_percent, 50)
        self.assertFalse(latest.is_overdue)

    def test_debtors_only_lists_customers_with_pending_receipts(self):
        debtors = list(self.client.get(reverse("home")).context["debtors"])
        self.assertEqual(debtors, [self.ana])
        self.assertEqual(debtors[0].pending_amount, Decimal("10"))

    def test_breakdowns_only_count_active_lines(self):
        ctx = self.client.get(reverse("home")).context
        by_location = {row["location__name"]: row["total"] for row in ctx["lines_by_location"]}
        self.assertEqual(by_location, {"Centro": 1, None: 2})
        by_fee = {row["fee__name"]: row["total"] for row in ctx["lines_by_fee"]}
        self.assertEqual(by_fee, {"Mensual": 2, None: 1})

    def test_empty_database_renders(self):
        InvoiceLine.objects.all().delete()
        Invoice.objects.all().delete()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Todavía no hay facturas registradas.")
