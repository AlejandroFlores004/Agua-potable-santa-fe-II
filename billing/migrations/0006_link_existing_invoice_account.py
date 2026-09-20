from django.db import migrations


def create_and_link_account(apps, schema_editor):
    Account = apps.get_model('billing', 'Account')
    Invoice = apps.get_model('billing', 'Invoice')

    invoice = Invoice.objects.order_by('id').first()
    if invoice is None:
        return

    account, _ = Account.objects.get_or_create(
        number="110000369974",
        defaults={"name": "Cuenta 1", "created_by_id": invoice.created_by_id},
    )
    invoice.account = account
    invoice.save(update_fields=["account"])


def reverse(apps, schema_editor):
    Account = apps.get_model('billing', 'Account')
    Account.objects.filter(number="110000369974").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0005_account_invoice_account'),
    ]

    operations = [
        migrations.RunPython(create_and_link_account, reverse),
    ]
