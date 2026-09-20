import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0006_link_existing_invoice_account'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='account',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='billing.account', verbose_name='Cuenta'),
        ),
    ]
