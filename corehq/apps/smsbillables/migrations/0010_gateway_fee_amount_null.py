from django.db import migrations, models

from corehq.apps.smsbillables.management.commands.bootstrap_gateway_fees import (
    bootstrap_twilio_gateway,
)


def add_twilio_gateway_fee_for_migration(apps, schema_editor):
    bootstrap_twilio_gateway(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0009_smsbillable_direct_gateway_fee'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsgatewayfee',
            name='amount',
            field=models.DecimalField(null=True, max_digits=10, decimal_places=4),
            preserve_default=True,
        ),
        migrations.RunPython(add_twilio_gateway_fee_for_migration),
    ]
