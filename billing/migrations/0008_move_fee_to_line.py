import django.db.models.deletion
from django.db import migrations, models


def move_fee_from_invoice_to_lines(apps, schema_editor):
    InvoiceLine = apps.get_model("billing", "InvoiceLine")
    Line = apps.get_model("connection", "Line")

    # Each assigned line keeps the fee (and amount) its invoice had.
    for invoice_line in InvoiceLine.objects.select_related("invoice__fee"):
        invoice_line.fee = invoice_line.invoice.fee
        invoice_line.amount = invoice_line.invoice.fee.amount
        invoice_line.save(update_fields=["fee", "amount"])

    # Each line takes the fee of the most recent invoice it was assigned to.
    for line in Line.objects.filter(fee__isnull=True):
        latest = (
            InvoiceLine.objects.filter(line=line)
            .select_related("invoice")
            .order_by("-invoice__start_date", "-created_at")
            .first()
        )
        if latest:
            line.fee_id = latest.invoice.fee_id
            line.save(update_fields=["fee"])


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0007_alter_invoice_account_required'),
        ('connection', '0005_line_fee'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoiceline',
            name='fee',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='billing.fee', verbose_name='Cuota'),
        ),
        migrations.AddField(
            model_name='invoiceline',
            name='amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Monto'),
        ),
        migrations.RunPython(move_fee_from_invoice_to_lines, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='invoice',
            name='fee',
        ),
    ]
