from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import ExpenseForm, RecurringExpenseForm
from .models import Expense, RecurringExpense, add_months


class AddMonthsTests(TestCase):
    def test_keeps_day_or_clamps_to_month_end(self):
        self.assertEqual(add_months(date(2026, 1, 15), 1), date(2026, 2, 15))
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_months(date(2026, 11, 30), 3), date(2027, 2, 28))


class RecurringExpenseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("admin", password="pass")
        self.client.force_login(self.user)

    def make_plan(self, **kwargs):
        defaults = {
            "name": "Luz de la bomba",
            "amount": Decimal("500"),
            "start_date": date(2026, 1, 31),
            "created_by": self.user,
        }
        defaults.update(kwargs)
        return RecurringExpense.objects.create(**defaults)

    def pay(self, plan, amount="500"):
        return Expense.objects.create(
            recurring=plan, concept=plan.name,
            amount=Decimal(amount), date=date.today(), created_by=self.user,
        )

    def test_next_due_date_advances_one_period_per_payment(self):
        plan = self.make_plan()
        self.assertEqual(plan.next_due_date, date(2026, 1, 31))
        self.pay(plan)
        self.assertEqual(plan.next_due_date, date(2026, 2, 28))
        self.pay(plan)
        self.assertEqual(plan.next_due_date, date(2026, 3, 31))

    def test_weekly_frequency(self):
        plan = self.make_plan(frequency=RecurringExpense.Frequency.WEEKLY, start_date=date(2026, 1, 1))
        self.pay(plan)
        self.assertEqual(plan.next_due_date, date(2026, 1, 8))

    def test_installments_finish_after_last_payment(self):
        plan = self.make_plan(kind=RecurringExpense.Kind.INSTALLMENTS, total_payments=2)
        self.pay(plan)
        self.assertFalse(plan.is_finished)
        self.assertEqual(plan.remaining_payments, 1)
        self.pay(plan)
        self.assertTrue(plan.is_finished)
        self.assertIsNone(plan.next_due_date)

    def test_end_date_finishes_plan(self):
        plan = self.make_plan(start_date=date(2026, 1, 1), end_date=date(2026, 1, 20))
        self.pay(plan)
        self.assertTrue(plan.is_finished)

    def test_overdue_when_next_payment_is_in_the_past(self):
        plan = self.make_plan(start_date=date.today() - timedelta(days=3))
        self.assertTrue(plan.is_overdue)
        future = self.make_plan(start_date=date.today() + timedelta(days=3))
        self.assertFalse(future.is_overdue)

    def test_installments_require_total_payments(self):
        form = RecurringExpenseForm({
            "name": "Bomba nueva", "kind": "installments",
            "amount": "1000", "frequency": "monthly", "start_date": "2026-01-01",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("total_payments", form.errors)

    def test_pay_view_creates_recurring_expense(self):
        plan = self.make_plan()
        response = self.client.post(reverse("recurring_pay", args=[plan.pk]), {
            "concept": plan.name, "amount": "612.40",
            "date": "2026-02-03",
        })
        self.assertEqual(response.status_code, 200)
        expense = plan.payments.get()
        self.assertEqual(expense.amount, Decimal("612.40"))

    def test_pay_view_rejects_finished_plan(self):
        plan = self.make_plan(kind=RecurringExpense.Kind.INSTALLMENTS, total_payments=1)
        self.pay(plan)
        self.client.post(reverse("recurring_pay", args=[plan.pk]), {
            "concept": plan.name, "amount": "500",
            "date": "2026-02-03",
        })
        self.assertEqual(plan.payments.count(), 1)

    def test_plan_with_payments_cannot_be_deleted(self):
        plan = self.make_plan()
        self.pay(plan)
        self.client.post(reverse("recurring_delete", args=[plan.pk]))
        self.assertTrue(RecurringExpense.objects.filter(pk=plan.pk).exists())

    def test_plan_without_payments_can_be_deleted(self):
        plan = self.make_plan()
        self.client.post(reverse("recurring_delete", args=[plan.pk]))
        self.assertFalse(RecurringExpense.objects.filter(pk=plan.pk).exists())

    def test_home_renders(self):
        self.make_plan()
        response = self.client.get(reverse("recurring_home"))
        self.assertContains(response, "Luz de la bomba")


class ExpenseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("admin", password="pass")
        self.client.force_login(self.user)

    def test_create_one_time_expense(self):
        self.client.post(reverse("expense_create"), {
            "concept": "Cambio de válvula",
            "amount": "350", "date": "2026-03-10",
        })
        expense = Expense.objects.get()
        self.assertEqual(expense.concept, "Cambio de válvula")
        self.assertEqual(expense.created_by, self.user)

    def test_amount_must_be_positive(self):
        form = ExpenseForm({
            "concept": "X",
            "amount": "0", "date": "2026-03-10",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)

    def test_home_filters_by_month_and_sums_total(self):
        for day, amount in [(date(2026, 3, 5), "100"), (date(2026, 3, 20), "50"), (date(2026, 4, 1), "999")]:
            Expense.objects.create(concept=f"Gasto {amount}", amount=Decimal(amount), date=day, created_by=self.user)

        response = self.client.get(reverse("expense_home"), {"month": "2026-03"})
        self.assertEqual(response.context["summary"]["total"], Decimal("150"))
        self.assertEqual(response.context["summary"]["other_total"], Decimal("150"))
        self.assertNotContains(response, "Gasto 999")

        response = self.client.get(reverse("expense_home"), {"month": ""})
        self.assertEqual(response.context["summary"]["total"], Decimal("1149"))

    def test_delete_expense(self):
        expense = Expense.objects.create(concept="X", amount=Decimal("10"), date=date.today(), created_by=self.user)
        self.client.post(reverse("expense_delete", args=[expense.pk]))
        self.assertFalse(Expense.objects.filter(pk=expense.pk).exists())


class ExpenseTemplatesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("admin", password="pass")
        self.client.force_login(self.user)
        self.plan = RecurringExpense.objects.create(
            name="Sueldo fontanero", amount=Decimal("3000"),
            start_date=date.today(), created_by=self.user,
        )
        self.expense = Expense.objects.create(
            concept="Cloro", amount=Decimal("80"), date=date.today(), created_by=self.user,
        )

    def test_pages_and_modals_render(self):
        urls = [
            reverse("expense_home"),
            reverse("expense_create"),
            reverse("expense_edit", args=[self.expense.pk]),
            reverse("recurring_home"),
            reverse("recurring_create"),
            reverse("recurring_edit", args=[self.plan.pk]),
            reverse("recurring_pay", args=[self.plan.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.get(url, headers={"HX-Request": "true"}).status_code, 200)
